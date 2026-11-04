"""mcp-telegram-agent 伺服器主體邏輯。

全功能 Telegram Bot 控制協議伺服器：文字通知、行內鍵盤、底部鍵盤、
本機檔案與多媒體相簿、互動元件、訊息生命週期維護。
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

import httpx

try:  # mcp >= 2.0
    from mcp.server.mcpserver import MCPServer
except ImportError:  # mcp 1.x
    from mcp.server.fastmcp import FastMCP as MCPServer

from pydantic import BaseModel, Field

mcp = MCPServer("TelegramAgentMCP")

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
DEFAULT_CHAT_ID = os.environ.get("TELEGRAM_DEFAULT_CHAT_ID")
API_BASE = f"https://api.telegram.org/bot{BOT_TOKEN}"

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
VIDEO_EXTS = {".mp4", ".avi", ".mkv", ".mov", ".webm"}

MISSING_CHAT_ID = "Error: Missing chat_id / 錯誤：缺少目標 chat_id"


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

    url = f"{API_BASE}/{endpoint}"
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            if files:
                resp = await client.post(url, data=payload, files=files)
            else:
                resp = await client.post(url, json=payload)

            result = resp.json()
            if resp.status_code == 200 and result.get("ok"):
                message_id = result.get("result", {}).get("message_id")
                return (
                    f"Success ({endpoint}), message ID: {message_id}"
                    if message_id
                    else f"Success ({endpoint})"
                )
            return f"Telegram API Error ({endpoint}): {result.get('description', resp.text)}"
        except Exception as e:
            return f"Connection Error ({endpoint}): {str(e)}"


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