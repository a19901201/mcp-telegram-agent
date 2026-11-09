"""mcp-telegram-agent 伺服器主體邏輯。

全功能 Telegram Bot 控制協議伺服器：文字通知、行內鍵盤、底部鍵盤、
本機檔案與多媒體相簿、互動元件、訊息生命週期維護，以及透過長輪詢
（long polling，不使用 webhook）接收使用者回覆的互動工具。
"""

import asyncio
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

import httpx

try:  # mcp >= 2.0
    from mcp.server.mcpserver import MCPServer
except ImportError:  # mcp 1.x
    from mcp.server.fastmcp import FastMCP as MCPServer

from pydantic import BaseModel, Field

mcp = MCPServer("TelegramAgentMCP")

# 兩個環境變數皆為選填：未設定時伺服器仍可正常啟動，
# 僅在實際呼叫需要權杖或預設 chat_id 的工具時回傳錯誤說明。
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
DEFAULT_CHAT_ID = os.environ.get("TELEGRAM_DEFAULT_CHAT_ID")
# 白名單：使用者必須主動設定才會收到互動回覆；未設定時接收工具會回傳
# 設定提示，讓 AI 知道需要補上 TELEGRAM_ALLOWED_CHAT_IDS 後重試。
ALLOWED_CHAT_IDS = os.environ.get("TELEGRAM_ALLOWED_CHAT_IDS")
ALLOWED_USER_IDS = os.environ.get("TELEGRAM_ALLOWED_USER_IDS")
STATE_DIR = os.environ.get("TELEGRAM_STATE_DIR")

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
VIDEO_EXTS = {".mp4", ".avi", ".mkv", ".mov", ".webm"}

MISSING_CHAT_ID = "Error: Missing chat_id / 錯誤：缺少目標 chat_id"
MISSING_ALLOWED_CHAT_IDS = (
    "Error: TELEGRAM_ALLOWED_CHAT_IDS is not set. / 錯誤：尚未設定 "
    "TELEGRAM_ALLOWED_CHAT_IDS。請在 MCP 設定檔 env 區塊加入 "
    "TELEGRAM_ALLOWED_CHAT_IDS=你的_CHAT_ID（多個以逗號分隔，如 "
    "123456789,-1001234567890），重啟 MCP 伺服器後再呼叫接收工具。\n"
    "Action required: add TELEGRAM_ALLOWED_CHAT_IDS to the MCP server env "
    "and restart the server before calling get_updates / wait_for_reply. / "
    "請提示使用者補上 TELEGRAM_ALLOWED_CHAT_IDS 後重試。"
)
MISSING_BOT_TOKEN = (
    "Error: TELEGRAM_BOT_TOKEN is not set. / 錯誤：未設定 TELEGRAM_BOT_TOKEN"
)


class InlineButton(BaseModel):
    text: str = Field(
        ...,
        description="Button label text / 按鈕顯示文字",
    )
    url: Optional[str] = Field(
        None,
        description="URL opened when clicked / 點擊後開啟的外部網址",
    )
    callback_data: Optional[str] = Field(
        None,
        description="Data sent back to the bot / 點擊後回傳機器人的資料字串",
    )


def _build_reply_markup(
    inline_buttons: Optional[List[List[InlineButton]]] = None,
    reply_keyboard: Optional[List[List[str]]] = None,
    one_time_keyboard: bool = True,
    remove_keyboard: bool = False,
) -> Optional[str]:
    """統整建構 Telegram 的 reply_markup JSON 字串。"""
    if remove_keyboard:
        return json.dumps({"remove_keyboard": True})

    if inline_buttons:
        keyboard = []
        for row in inline_buttons:
            row_btns = []
            for btn in row:
                item: Dict[str, Any] = {"text": btn.text}
                if btn.url:
                    item["url"] = btn.url
                elif btn.callback_data:
                    item["callback_data"] = btn.callback_data
                else:
                    item["callback_data"] = btn.text
                row_btns.append(item)
            keyboard.append(row_btns)
        return json.dumps({"inline_keyboard": keyboard})

    if reply_keyboard:
        keyboard = [[{"text": text} for text in row] for row in reply_keyboard]
        return json.dumps(
            {
                "keyboard": keyboard,
                "resize_keyboard": True,
                "one_time_keyboard": one_time_keyboard,
            }
        )

    return None


async def _execute_post(
    endpoint: str, payload: dict, files: Optional[dict] = None
) -> str:
    """發送請求至 Telegram API 並回傳標準結果。"""
    if not BOT_TOKEN:
        return "Error: TELEGRAM_BOT_TOKEN environment variable is not set. / 錯誤：未設定 TELEGRAM_BOT_TOKEN 環境變數"

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/{endpoint}"
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            if files:
                resp = await client.post(url, data=payload, files=files)
            else:
                resp = await client.post(url, json=payload)

            result = resp.json()
            if resp.status_code == 200 and result.get("ok"):
                raw_result = result.get("result")
                # sendChatAction、answerCallbackQuery 等回傳 true，僅文字/檔案類回傳物件
                if isinstance(raw_result, dict):
                    message_id = raw_result.get("message_id")
                    return (
                        f"Success ({endpoint}), message ID: {message_id}"
                        if message_id
                        else f"Success ({endpoint})"
                    )
                return f"Success ({endpoint})"
            return f"Telegram API Error ({endpoint}): {result.get('description', resp.text)}"
        except Exception as e:
            return f"Connection Error ({endpoint}): {str(e)}"


# =====================================================================
# 接收層（getUpdates 長輪詢，不使用 webhook）
# =====================================================================

ReceiveType = Literal["message", "callback_query", "poll_answer"]

_ALLOWED_UPDATES = ["message", "callback_query", "poll_answer"]


def _parse_id_list(raw: Optional[str]) -> List[str]:
    """把逗號分隔的 ID 字串解析成字串清單（保留負號，去除空白）。"""
    if not raw:
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


def _state_file() -> Path:
    """取得 offset 持久化檔案路徑；預設寫在使用者暫存目錄。"""
    base = Path(STATE_DIR) if STATE_DIR else Path(tempfile.gettempdir()) / "mcp-telegram-agent"
    base.mkdir(parents=True, exist_ok=True)
    return base / "updates_state.json"


def _load_offset() -> int:
    """讀取上次處理到的 update_id；檔案不存在或格式異常時回 0。"""
    path = _state_file()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return int(data.get("offset", 0))
    except (FileNotFoundError, json.JSONDecodeError, TypeError, ValueError):
        return 0


def _save_offset(offset: int) -> None:
    """把最新 offset 寫回狀態檔，避免 MCP 重啟後重複讀取舊訊息。"""
    path = _state_file()
    try:
        path.write_text(json.dumps({"offset": offset}), encoding="utf-8")
    except OSError:
        pass


def _normalize_update(update: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """把 Telegram update 原始物件歸一化成單一格式。

    回傳 dict 一律含：type、update_id、chat_id、user_id、text、payload。
    不屬於三種支援型別時回 None。
    """
    update_id = update.get("update_id")
    if update_id is None:
        return None

    if "message" in update and isinstance(update["message"], dict):
        msg = update["message"]
        chat = msg.get("chat", {})
        return {
            "type": "message",
            "update_id": update_id,
            "chat_id": chat.get("id"),
            "user_id": (msg.get("from") or {}).get("id"),
            "text": msg.get("text") or msg.get("caption") or "",
            "payload": {
                "message_id": msg.get("message_id"),
                "reply_to_message_id": (msg.get("reply_to_message") or {}).get("message_id"),
                "date": msg.get("date"),
            },
        }

    if "callback_query" in update and isinstance(update["callback_query"], dict):
        cb = update["callback_query"]
        msg = cb.get("message") or {}
        chat = msg.get("chat") or {}
        return {
            "type": "callback_query",
            "update_id": update_id,
            "chat_id": chat.get("id"),
            "user_id": (cb.get("from") or {}).get("id"),
            "text": cb.get("data") or "",
            "payload": {
                "callback_query_id": cb.get("id"),
                "message_id": msg.get("message_id"),
            },
        }

    if "poll_answer" in update and isinstance(update["poll_answer"], dict):
        pa = update["poll_answer"]
        return {
            "type": "poll_answer",
            "update_id": update_id,
            "chat_id": None,  # poll_answer 沒有 chat_id，僅能以 user_id 或 poll_id 對應
            "user_id": (pa.get("user") or {}).get("id"),
            "text": "",
            "payload": {
                "poll_id": pa.get("poll_id"),
                "option_ids": pa.get("option_ids"),
            },
        }

    return None


def _filter_updates(
    normalized: List[Dict[str, Any]],
    allowed_chat_ids: List[str],
    allowed_user_ids: List[str],
    wanted_types: List[str],
    chat_id_hint: Optional[str],
) -> List[Dict[str, Any]]:
    """依白名單（聊天室／使用者）與型別過濾歸一化後的更新。

    語意為「已設定的名單中，至少一個命中即放行」（OR）：
    - 僅設 chat 名單 → 只依 chat_id 過濾；
    - 僅設 user 名單 → 只依 user_id 過濾；
    - 兩份都設 → 任一命中即放行（未設定的名單不參與判定）。
    兩者皆未設定時不過濾（由 _validate_receive_env 擋下此情況）。
    poll_answer 沒有 chat_id，無法與 chat 名單比對；僅設 chat 名單時
    其不受 chat 名單影響，需靠 user 名單過濾。
    """
    result: List[Dict[str, Any]] = []
    for item in normalized:
        if item["type"] not in wanted_types:
            continue
        chat_id = item.get("chat_id")
        user_id = item.get("user_id")
        evaluable = 0  # 已設定且可與此事件比對的名單數
        passed = 0  # 其中命中的名單數
        for allowed, id_val in (
            (allowed_chat_ids, chat_id),
            (allowed_user_ids, user_id),
        ):
            if not allowed or id_val is None:
                continue  # 名單未設定或事件無此維度 ID，皆不適用
            evaluable += 1
            if str(id_val) in allowed:
                passed += 1
        # 有可評估名單時必須命中其一；完全無法評估時放行
        if evaluable and not passed:
            continue
        if chat_id_hint and chat_id is not None and str(chat_id) != chat_id_hint:
            continue
        result.append(item)
    return result


async def _get_updates_once(
    offset: int,
    timeout_s: int,
    allowed_updates: List[str],
) -> tuple[Optional[List[Dict[str, Any]]], Optional[str]]:
    """呼叫一次 getUpdates；回傳 (原始 updates 清單, 錯誤訊息)。

    長輪詢 timeout 上限 50 秒（Telegram API 限制）。
    """
    if not BOT_TOKEN:
        return None, MISSING_BOT_TOKEN

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
    payload = {
        "offset": offset if offset > 0 else None,
        "timeout": min(timeout_s, 50),
        "allowed_updates": allowed_updates,
    }
    payload = {k: v for k, v in payload.items() if v is not None}

    try:
        async with httpx.AsyncClient(timeout=timeout_s + 10.0) as client:
            resp = await client.post(url, json=payload)
            result = resp.json()
    except Exception as e:
        return None, f"Connection Error (getUpdates): {str(e)}"

    if resp.status_code == 200 and result.get("ok"):
        return result.get("result") or [], None

    desc = result.get("description", resp.text) if isinstance(result, dict) else resp.text
    # 同一 token 只能有一個輪詢者，409 衝突為常見不可重試錯誤
    return None, f"Telegram API Error (getUpdates): {desc}"


def _validate_receive_env() -> Optional[str]:
    """接收工具的前置檢查：回傳錯誤訊息或 None（通過）。"""
    if not BOT_TOKEN:
        return MISSING_BOT_TOKEN
    if not _parse_id_list(ALLOWED_CHAT_IDS) and not _parse_id_list(ALLOWED_USER_IDS):
        return MISSING_ALLOWED_CHAT_IDS
    return None


@mcp.tool()
async def get_updates(
    chat_id: Optional[str] = None,
    types: Optional[List[ReceiveType]] = None,
    limit: int = 20,
    mark_read: bool = True,
) -> str:
    """Fetch pending user updates (messages, button clicks, poll answers) once without waiting.

    一次性拉取待處理的更新並歸一化回傳，不等待新訊息。
    chat_id 未傳時使用 TELEGRAM_DEFAULT_CHAT_ID；未設定白名單時回傳設定提示。
    types 可選 message、callback_query、poll_answer，預設全部。
    mark_read=False 時不移動 offset，同一批訊息下次仍會回傳（預設會讀取並推進）。
    limit 只限制單次回傳筆數：offset 僅推進到實際回傳的最後一筆，
    截斷的其餘符合項目會留待下次呼叫；無符合項時整批消耗（含白名單外
    與 types 以外的更新）以免積壓堆積——offset 為單一串流，無法單獨
    保留某個型別或某間聊天室的更新。
    注意：首次呼叫（尚無狀態檔）時 Telegram 會回傳全部未確認的 pending
    updates，且 mark_read 預設 true 會將其讀取推進；若不想消耗歷史積壓，
    第一次呼叫請先以 mark_read=False 預覽。
    """
    env_err = _validate_receive_env()
    if env_err:
        return env_err

    allowed_chat_ids = _parse_id_list(ALLOWED_CHAT_IDS)
    allowed_user_ids = _parse_id_list(ALLOWED_USER_IDS)
    wanted_types = types or ["message", "callback_query", "poll_answer"]
    chat_hint = chat_id or DEFAULT_CHAT_ID

    offset = _load_offset()
    raw_updates, err = await _get_updates_once(
        offset=offset, timeout_s=2, allowed_updates=_ALLOWED_UPDATES
    )
    if err:
        return err

    normalized: List[Dict[str, Any]] = []
    max_id = offset
    for u in raw_updates:
        item = _normalize_update(u)
        if item:
            normalized.append(item)
            max_id = max(max_id, item["update_id"] + 1)

    filtered = _filter_updates(
        normalized, allowed_chat_ids, allowed_user_ids, wanted_types, chat_hint
    )
    filtered = filtered[: max(1, limit)]

    next_offset = offset
    if mark_read:
        if filtered:
            # offset 只推進到實際回傳的最後一筆：limit 截斷的其餘符合
            # 項目留待下次呼叫，不會因截斷而被靜默消耗；其前的非符合
            # 項與不支援型別會依 Telegram offset 語意一併確認
            next_offset = max(item["update_id"] for item in filtered) + 1
            _save_offset(next_offset)
        else:
            # 無符合項時整批消耗，避免白名單外訊息無限堆積
            _save_offset(max_id)
            next_offset = max_id

    if not filtered:
        return (
            f"No pending updates matching filter. / 沒有符合條件的待處理更新"
            f"（offset={max_id}）"
        )

    return json.dumps(
        {
            "count": len(filtered),
            "next_offset": next_offset,
            "updates": filtered,
        },
        ensure_ascii=False,
        indent=2,
    )


@mcp.tool()
async def wait_for_reply(
    chat_id: Optional[str] = None,
    types: Optional[List[ReceiveType]] = None,
    timeout: int = 25,
    poll_interval: int = 2,
) -> str:
    """Wait for the next user reply (message, button click, or poll answer) via long polling.

    長輪詢等待使用者下一則回覆（訊息／按鈕點擊／投票作答）。
    連續長輪詢（每段最長 10 秒）直到 timeout 秒內出現符合項目或逾時；
    poll_interval 僅用於網路錯誤後的退避等待（至少 1 秒），正常情況下不會隔段輪詢。
    未設定白名單時回傳設定提示，請 AI 提醒使用者補上 TELEGRAM_ALLOWED_CHAT_IDS 後重啟。
    注意：
    - 首次呼叫（尚無狀態檔）時會先撈回全部 pending updates，最舊的先被
      比對回傳；建議先以 get_updates(mark_read=False) 預覽確認沒有積壓。
    - types 以外的更新仍會被讀取推進（offset 單一串流，無法單獨保留）；
      若等待訊息期間按鈕被點擊，該 callback_query 會被消耗而不回傳，
      需要接收點擊事件時請讓 types 涵蓋 callback_query。
    """
    env_err = _validate_receive_env()
    if env_err:
        return env_err

    allowed_chat_ids = _parse_id_list(ALLOWED_CHAT_IDS)
    allowed_user_ids = _parse_id_list(ALLOWED_USER_IDS)
    wanted_types = types or ["message", "callback_query", "poll_answer"]
    chat_hint = chat_id or DEFAULT_CHAT_ID
    deadline = asyncio.get_event_loop().time() + max(1, timeout)

    offset = _load_offset()
    while True:
        remaining = deadline - asyncio.get_event_loop().time()
        if remaining <= 0:
            return (
                f"Timeout: no matching reply within {timeout}s. / "
                f"逾時：{timeout} 秒內未收到符合的回覆"
            )

        slice_s = min(max(1, int(remaining)), 10)
        raw_updates, err = await _get_updates_once(
            offset=offset, timeout_s=slice_s, allowed_updates=_ALLOWED_UPDATES
        )
        if err:
            # 409 衝突等不可重試錯誤直接回傳；網路抖動則退避後續試
            if "409" in err or "Conflict" in err:
                return err
            # 退避至少 1 秒（poll_interval<=0 時避免緊密重試），且不睡過 deadline
            await asyncio.sleep(min(max(1, int(poll_interval)), remaining))
            continue

        for u in raw_updates:
            item = _normalize_update(u)
            if not item:
                continue
            offset = max(offset, item["update_id"] + 1)
            matched = _filter_updates(
                [item], allowed_chat_ids, allowed_user_ids, wanted_types, chat_hint
            )
            if matched:
                _save_offset(offset)
                return json.dumps(
                    {"count": 1, "next_offset": offset, "updates": matched},
                    ensure_ascii=False,
                    indent=2,
                )
        # 這批沒有符合者，offset 已推進，存檔避免重複讀取
        _save_offset(offset)


@mcp.tool()
async def answer_callback_query(
    callback_query_id: str,
    text: str = "",
    show_alert: bool = False,
    url: Optional[str] = None,
    cache_time: int = 0,
) -> str:
    """Acknowledge a callback button press so the loading spinner on the button stops.

    對使用者點擊的行內按鈕回應，關閉按鈕上的載入動畫；text 可顯示小提示。
    callback_query_id 來自 get_updates / wait_for_reply 的 callback_query 事件。

    url 傳入時以開啟網址取代 text 提示（須為 http/https 開頭），
    並與 text 互斥（兩者不可同時傳入）；cache_time 為結果快取秒數
    （0-604800），預設 0。
    show_alert=True 時必須帶 text，否則回傳錯誤。
    注意：callback_query 只有數秒有效，get_updates / wait_for_reply 回傳後
    應立刻呼叫本工具；輪詢架構下若間隔過長會收到 query is too old，
    建議搭配 wait_for_reply 的長輪詢，或背景常駐輪詢並立即應答。
    """
    if not BOT_TOKEN:
        return MISSING_BOT_TOKEN
    if not callback_query_id or not str(callback_query_id).strip():
        return (
            "Error: callback_query_id is required. / "
            "錯誤：callback_query_id 為必填"
        )
    if len(text) > 200:
        return (
            "Error: text must be at most 200 characters. / "
            "錯誤：text 長度不可超過 200 字"
        )
    if show_alert and not text:
        return (
            "Error: text is required when show_alert is True. / "
            "錯誤：show_alert=True 時 text 為必填"
        )
    if text and url:
        return (
            "Error: text and url are mutually exclusive. / "
            "錯誤：text 與 url 不可同時傳入"
        )
    if url is not None and not str(url).startswith(("http://", "https://")):
        return (
            "Error: url must start with http:// or https:// / "
            "錯誤：url 須以 http:// 或 https:// 開頭"
        )
    if not 0 <= cache_time <= 604800:
        return (
            "Error: cache_time must be between 0 and 604800. / "
            "錯誤：cache_time 須介於 0 與 604800 之間"
        )

    payload: Dict[str, Any] = {
        "callback_query_id": callback_query_id,
        "show_alert": show_alert,
        "cache_time": cache_time,
    }
    if text:
        payload["text"] = text
    if url:
        payload["url"] = url
    return await _execute_post("answerCallbackQuery", payload)


# =====================================================================
# 1. 訊息與對話控制
# =====================================================================


@mcp.tool()
async def send_text_message(
    text: str,
    chat_id: Optional[str] = None,
    parse_mode: Literal["Markdown", "HTML"] = "Markdown",
    disable_notification: bool = False,
    protect_content: bool = False,
    inline_buttons: Optional[List[List[InlineButton]]] = None,
    reply_keyboard: Optional[List[List[str]]] = None,
    one_time_keyboard: bool = True,
    remove_keyboard: bool = False,
) -> str:
    """Send text messages with Markdown/HTML formatting, silent mode, protection, inline buttons, or custom reply keyboards.

    發送文字訊息。支援 Markdown 與 HTML 格式解析、靜音推播、內容保護、行內按鈕與底部鍵盤。
    """
    target = chat_id or DEFAULT_CHAT_ID
    if not target:
        return MISSING_CHAT_ID

    payload: Dict[str, Any] = {
        "chat_id": target,
        "text": text,
        "parse_mode": parse_mode,
        "disable_notification": disable_notification,
        "protect_content": protect_content,
    }

    markup = _build_reply_markup(
        inline_buttons, reply_keyboard, one_time_keyboard, remove_keyboard
    )
    if markup:
        payload["reply_markup"] = markup

    return await _execute_post("sendMessage", payload)


@mcp.tool()
async def send_chat_action(
    action: Literal[
        "typing",
        "upload_document",
        "upload_photo",
        "record_video",
        "upload_video",
        "record_voice",
        "upload_voice",
        "find_location",
    ] = "typing",
    chat_id: Optional[str] = None,
) -> str:
    """Broadcast ongoing bot status to the user (e.g., typing, uploading document, recording).

    向使用者廣播機器人當前的操作狀態，如打字中、上傳檔案中等。
    """
    target = chat_id or DEFAULT_CHAT_ID
    if not target:
        return MISSING_CHAT_ID

    payload = {"chat_id": target, "action": action}
    return await _execute_post("sendChatAction", payload)


# =====================================================================
# 2. 本地實體檔案與各類媒體
# =====================================================================


@mcp.tool()
async def send_local_document(
    file_path: str,
    caption: str = "",
    chat_id: Optional[str] = None,
    parse_mode: Literal["Markdown", "HTML"] = "Markdown",
    disable_notification: bool = False,
    inline_buttons: Optional[List[List[InlineButton]]] = None,
) -> str:
    """Send any local file (code, reports, logs, zip, pdf) as a general document.

    傳送本機任何檔案給使用者，涵蓋程式碼、日誌、PDF 與壓縮檔等。
    """
    target = chat_id or DEFAULT_CHAT_ID
    if not target:
        return MISSING_CHAT_ID

    path = Path(file_path)
    if not path.is_file():
        return f"Error: File not found: {file_path} / 錯誤：找不到檔案 {file_path}"

    payload: Dict[str, Any] = {
        "chat_id": target,
        "caption": caption,
        "parse_mode": parse_mode,
        "disable_notification": disable_notification,
    }

    markup = _build_reply_markup(inline_buttons=inline_buttons)
    if markup:
        payload["reply_markup"] = markup

    with open(path, "rb") as f:
        files = {"document": (path.name, f)}
        return await _execute_post("sendDocument", payload, files)


@mcp.tool()
async def send_local_photo(
    photo_path: str,
    caption: str = "",
    chat_id: Optional[str] = None,
    parse_mode: Literal["Markdown", "HTML"] = "Markdown",
    inline_buttons: Optional[List[List[InlineButton]]] = None,
) -> str:
    """Send a local image file as a full-preview photo.

    發送本機圖片檔案，以照片預覽格式呈現。
    """
    target = chat_id or DEFAULT_CHAT_ID
    if not target:
        return MISSING_CHAT_ID

    path = Path(photo_path)
    if not path.is_file():
        return f"Error: Image not found: {photo_path} / 錯誤：找不到圖片檔案 {photo_path}"

    payload: Dict[str, Any] = {
        "chat_id": target,
        "caption": caption,
        "parse_mode": parse_mode,
    }

    markup = _build_reply_markup(inline_buttons=inline_buttons)
    if markup:
        payload["reply_markup"] = markup

    with open(path, "rb") as f:
        files = {"photo": (path.name, f)}
        return await _execute_post("sendPhoto", payload, files)


@mcp.tool()
async def send_local_video(
    video_path: str,
    caption: str = "",
    duration: Optional[int] = None,
    width: Optional[int] = None,
    height: Optional[int] = None,
    supports_streaming: bool = True,
    chat_id: Optional[str] = None,
    inline_buttons: Optional[List[List[InlineButton]]] = None,
) -> str:
    """Send a local video file (MP4, etc.) as a playable streaming video.

    發送本機影片檔案，以內嵌播放器形式呈現，支援串流播放。
    """
    target = chat_id or DEFAULT_CHAT_ID
    if not target:
        return MISSING_CHAT_ID

    path = Path(video_path)
    if not path.is_file():
        return f"Error: Video not found: {video_path} / 錯誤：找不到影片檔案 {video_path}"

    payload: Dict[str, Any] = {
        "chat_id": target,
        "caption": caption,
        "parse_mode": "Markdown",
        "supports_streaming": supports_streaming,
    }
    if duration is not None:
        payload["duration"] = duration
    if width is not None:
        payload["width"] = width
    if height is not None:
        payload["height"] = height

    markup = _build_reply_markup(inline_buttons=inline_buttons)
    if markup:
        payload["reply_markup"] = markup

    with open(path, "rb") as f:
        files = {"video": (path.name, f)}
        return await _execute_post("sendVideo", payload, files)


@mcp.tool()
async def send_local_audio_or_voice(
    file_path: str,
    mode: Literal["audio", "voice"] = "audio",
    caption: str = "",
    title: str = "",
    performer: str = "",
    duration: Optional[int] = None,
    chat_id: Optional[str] = None,
    inline_buttons: Optional[List[List[InlineButton]]] = None,
) -> str:
    """Send a local audio file as a music track or a native voice note (OGG/Opus recommended).

    發送本機音訊檔案：mode=audio 以音樂曲目呈現（可附標題與演出者）；
    mode=voice 以原生語音訊息呈現（建議使用 OGG/Opus 編碼）。
    """
    target = chat_id or DEFAULT_CHAT_ID
    if not target:
        return MISSING_CHAT_ID

    path = Path(file_path)
    if not path.is_file():
        return f"Error: Audio file not found: {file_path} / 錯誤：找不到音訊檔案 {file_path}"

    payload: Dict[str, Any] = {
        "chat_id": target,
        "caption": caption,
        "parse_mode": "Markdown",
    }
    if duration is not None:
        payload["duration"] = duration

    markup = _build_reply_markup(inline_buttons=inline_buttons)
    if markup:
        payload["reply_markup"] = markup

    if mode == "voice":
        if title or performer:
            return "Error: title/performer are only supported in audio mode. / 錯誤：title 與 performer 僅支援 audio 模式"
        field = "voice"
        endpoint = "sendVoice"
    else:
        field = "audio"
        endpoint = "sendAudio"
        if title:
            payload["title"] = title
        if performer:
            payload["performer"] = performer

    with open(path, "rb") as f:
        files = {field: (path.name, f)}
        return await _execute_post(endpoint, payload, files)


@mcp.tool()
async def send_media_album(
    file_paths: List[str],
    caption: str = "",
    chat_id: Optional[str] = None,
    disable_notification: bool = False,
    protect_content: bool = False,
) -> str:
    """Send 2 to 10 local photos or videos as a single grouped album (carousel).

    批次發送 2 至 10 個本機圖片或影片，組合成輪播相簿。
    """
    target = chat_id or DEFAULT_CHAT_ID
    if not target:
        return MISSING_CHAT_ID

    if len(file_paths) < 2 or len(file_paths) > 10:
        return "Error: Album must contain between 2 and 10 files. / 錯誤：相簿必須包含 2 至 10 個檔案"

    files: Dict[str, Any] = {}
    media: List[Dict[str, Any]] = []
    for i, fp in enumerate(file_paths):
        path = Path(fp)
        if not path.is_file():
            return f"Error: File not found: {fp} / 錯誤：找不到檔案 {fp}"
        ext = path.suffix.lower()
        if ext in IMAGE_EXTS:
            media_type = "photo"
        elif ext in VIDEO_EXTS:
            media_type = "video"
        else:
            return f"Error: Unsupported album file type: {fp} / 錯誤：相簿不支援此檔案類型 {fp}"

        field = f"file{i}"
        files[field] = (path.name, open(path, "rb"))
        media.append({"type": media_type, "media": f"attach://{field}"})

    media[0]["caption"] = caption
    media[0]["parse_mode"] = "Markdown"

    payload: Dict[str, Any] = {
        "chat_id": target,
        "media": json.dumps(media),
        "disable_notification": disable_notification,
        "protect_content": protect_content,
    }

    try:
        return await _execute_post("sendMediaGroup", payload, files)
    finally:
        for f in files.values():
            f[1].close()


# =====================================================================
# 3. 互動卡片與專用元件
# =====================================================================


@mcp.tool()
async def send_poll(
    question: str,
    options: List[str],
    type: Literal["quiz", "regular"] = "regular",
    is_anonymous: bool = True,
    allows_multiple_answers: bool = False,
    correct_option_id: Optional[int] = None,
    explanation: str = "",
    chat_id: Optional[str] = None,
) -> str:
    """Send a poll or quiz card with clickable options.

    發送投票或測驗卡片，供使用者點選。type=quiz 時可指定正確選項與解析說明。
    """
    target = chat_id or DEFAULT_CHAT_ID
    if not target:
        return MISSING_CHAT_ID

    if type == "quiz":
        if correct_option_id is None:
            return "Error: Quiz type requires correct_option_id. / 錯誤：測驗模式必須提供正確選項編號"
        if len(options) < 2 or len(options) > 10:
            return "Error: Poll options must contain between 2 and 10 items. / 錯誤：選項數量必須介於 2 至 10 個"

    payload: Dict[str, Any] = {
        "chat_id": target,
        "question": question,
        "options": json.dumps(options),
        "type": type,
        "is_anonymous": is_anonymous,
    }
    if type == "regular":
        payload["allows_multiple_answers"] = allows_multiple_answers
    else:
        payload["correct_option_id"] = correct_option_id
        if explanation:
            payload["explanation"] = explanation

    return await _execute_post("sendPoll", payload)


@mcp.tool()
async def send_location(latitude: float, longitude: float, chat_id: Optional[str] = None) -> str:
    """Send a geographic location card that opens directly in the map app.

    發送地理位置卡片，可直接開啟地圖導航。
    """
    target = chat_id or DEFAULT_CHAT_ID
    if not target:
        return MISSING_CHAT_ID

    payload = {"chat_id": target, "latitude": latitude, "longitude": longitude}
    return await _execute_post("sendLocation", payload)


@mcp.tool()
async def send_contact(phone_number: str, first_name: str, last_name: str = "", chat_id: Optional[str] = None) -> str:
    """Send a vCard contact so the user can save it to their address book.

    發送名片聯絡人，可儲存至通訊錄。
    """
    target = chat_id or DEFAULT_CHAT_ID
    if not target:
        return MISSING_CHAT_ID

    payload: Dict[str, Any] = {
        "chat_id": target,
        "phone_number": phone_number,
        "first_name": first_name,
        "last_name": last_name,
    }
    return await _execute_post("sendContact", payload)


@mcp.tool()
async def send_dice(
    emoji: Literal["🎲", "🎯", "🏀", "⚽", "🎳", "🎰"] = "🎲", chat_id: Optional[str] = None
) -> str:
    """Send an animated random-value emoji (dice, dart, basketball, football, bowling, slot machine).

    發送擲骰子等動態隨機結果的動畫元件。
    """
    target = chat_id or DEFAULT_CHAT_ID
    if not target:
        return MISSING_CHAT_ID

    payload = {"chat_id": target, "emoji": emoji}
    return await _execute_post("sendDice", payload)


# =====================================================================
# 4. 訊息生命週期維護
# =====================================================================


@mcp.tool()
async def edit_message_text(
    message_id: int,
    text: str,
    chat_id: Optional[str] = None,
    parse_mode: Literal["Markdown", "HTML"] = "Markdown",
    inline_buttons: Optional[List[List[InlineButton]]] = None,
    reply_keyboard: Optional[List[List[str]]] = None,
    one_time_keyboard: bool = True,
    remove_keyboard: bool = False,
) -> str:
    """Edit the text or keyboard of a previously sent message (does not work for media albums).

    編輯先前已發送的文字訊息內容或鍵盤佈局。
    """
    target = chat_id or DEFAULT_CHAT_ID
    if not target:
        return MISSING_CHAT_ID

    payload: Dict[str, Any] = {
        "chat_id": target,
        "message_id": message_id,
        "text": text,
        "parse_mode": parse_mode,
    }

    markup = _build_reply_markup(
        inline_buttons, reply_keyboard, one_time_keyboard, remove_keyboard
    )
    payload["reply_markup"] = markup if markup else json.dumps({"inline_keyboard": []})

    return await _execute_post("editMessageText", payload)


@mcp.tool()
async def delete_message(message_id: int, chat_id: Optional[str] = None) -> str:
    """Delete a specific message by ID (can only delete messages sent by the bot).

    刪除指定 ID 的訊息（僅能刪除機器人自己發送的訊息）。
    """
    target = chat_id or DEFAULT_CHAT_ID
    if not target:
        return MISSING_CHAT_ID

    payload = {"chat_id": target, "message_id": message_id}
    return await _execute_post("deleteMessage", payload)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()