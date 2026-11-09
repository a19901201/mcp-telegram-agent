"""接收工具（get_updates / wait_for_reply / answer_callback_query）單元測試。

覆蓋白名單解析、offset 持久化、update 歸一化、過濾邏輯與前置檢查；
全程以 monkeypatch 替換模組層常數，不觸發真實 Telegram API 呼叫。
"""

import asyncio
import json

import pytest

import mcp_telegram_agent.server as server


@pytest.fixture()
def state_dir(tmp_path, monkeypatch):
    """把狀態檔導向暫存測試目錄，避免污染實際環境。"""
    monkeypatch.setattr(server, "STATE_DIR", str(tmp_path))
    return tmp_path


@pytest.fixture()
def fake_token(monkeypatch):
    """提供假的 BOT_TOKEN，讓 _validate_receive_env 的第一層檢查通過。"""
    monkeypatch.setattr(server, "BOT_TOKEN", "123456:fake-token")


@pytest.fixture()
def whitelisted(monkeypatch):
    """模擬已設定 TELEGRAM_ALLOWED_CHAT_IDS。"""
    monkeypatch.setattr(server, "ALLOWED_CHAT_IDS", "123456789")
    monkeypatch.setattr(server, "ALLOWED_USER_IDS", "")


@pytest.fixture()
def no_whitelist(monkeypatch):
    """模擬完全未設定白名單。"""
    monkeypatch.setattr(server, "ALLOWED_CHAT_IDS", "")
    monkeypatch.setattr(server, "ALLOWED_USER_IDS", "")


# =====================================================================
# 白名單解析
# =====================================================================


def test_parse_id_list_basic():
    assert server._parse_id_list("123456789,-1001234567890") == [
        "123456789",
        "-1001234567890",
    ]


def test_parse_id_list_strips_whitespace_and_drops_empty():
    assert server._parse_id_list(" 111 ,, , 222 ") == ["111", "222"]
    assert server._parse_id_list("") == []
    assert server._parse_id_list(None) == []


# =====================================================================
# offset 持久化
# =====================================================================


def test_load_offset_defaults_to_zero(state_dir):
    assert server._load_offset() == 0


def test_save_then_load_offset_roundtrip(state_dir):
    server._save_offset(4242)
    assert server._load_offset() == 4242
    assert json.loads(
        (state_dir / "updates_state.json").read_text(encoding="utf-8")
    ) == {"offset": 4242}


def test_load_offset_survives_corrupt_file(state_dir):
    (state_dir / "updates_state.json").write_text("not-json{", encoding="utf-8")
    assert server._load_offset() == 0


def test_state_file_created_inside_configured_dir(state_dir):
    server._save_offset(7)
    assert (state_dir / "updates_state.json").exists()




# =====================================================================
# update 歸一化
# =====================================================================


def test_normalize_message_update():
    update = {
        "update_id": 1,
        "message": {
            "message_id": 10,
            "date": 1700000000,
            "text": "hello",
            "from": {"id": 111},
            "chat": {"id": 222},
        },
    }
    item = server._normalize_update(update)
    assert item["type"] == "message"
    assert item["update_id"] == 1
    assert item["chat_id"] == 222
    assert item["user_id"] == 111
    assert item["text"] == "hello"
    assert item["payload"]["message_id"] == 10


def test_normalize_callback_query_update():
    update = {
        "update_id": 2,
        "callback_query": {
            "id": "cbq-1",
            "data": "action=delete",
            "from": {"id": 111},
            "message": {"message_id": 20, "chat": {"id": 222}},
        },
    }
    item = server._normalize_update(update)
    assert item["type"] == "callback_query"
    assert item["text"] == "action=delete"
    assert item["payload"]["callback_query_id"] == "cbq-1"
    assert item["payload"]["message_id"] == 20


def test_normalize_poll_answer_has_no_chat_id():
    update = {
        "update_id": 3,
        "poll_answer": {"poll_id": "p1", "option_ids": [0, 2], "user": {"id": 333}},
    }
    item = server._normalize_update(update)
    assert item["type"] == "poll_answer"
    assert item["chat_id"] is None
    assert item["user_id"] == 333
    assert item["payload"]["option_ids"] == [0, 2]


def test_normalize_skips_unsupported_and_malformed():
    assert server._normalize_update({"update_id": 4, "my_chat_member": {}}) is None
    assert server._normalize_update({"message": "no update_id"}) is None


# =====================================================================
# 過濾邏輯（chat/user 白名單 OR、型別、chat_id_hint）
# =====================================================================


def _msg(update_id, chat_id, user_id):
    return {
        "type": "message",
        "update_id": update_id,
        "chat_id": chat_id,
        "user_id": user_id,
        "text": "hi",
        "payload": {},
    }


def test_filter_keeps_allowed_chat():
    # user 白名單需設為不命中的清單，才能單獨驗證 chat 維度
    items = [_msg(1, 222, 111), _msg(2, 999, 111)]
    out = server._filter_updates(items, ["222"], ["555"], ["message"], None)
    assert [i["update_id"] for i in out] == [1]


def test_filter_keeps_allowed_user():
    # chat 白名單需設為不命中的清單，才能單獨驗證 user 維度
    items = [_msg(1, 222, 111), _msg(2, 999, 999)]
    out = server._filter_updates(items, ["555"], ["111"], ["message"], None)
    assert [i["update_id"] for i in out] == [1]


def test_filter_blocks_when_both_lists_miss():
    items = [_msg(1, 999, 999)]
    assert server._filter_updates(items, ["222"], ["111"], ["message"], None) == []


def test_filter_wanted_types():
    items = [_msg(1, 222, 111)]
    assert server._filter_updates(items, [], [], ["callback_query"], None) == []
    assert server._filter_updates(items, [], [], ["message"], None) == items


def test_filter_chat_id_hint_narrows():
    items = [_msg(1, 222, 111), _msg(2, 999, 111)]
    out = server._filter_updates(items, [], [], ["message"], "222")
    assert [i["update_id"] for i in out] == [1]


def test_filter_poll_answer_passes_via_user_list():
    poll = {
        "type": "poll_answer",
        "update_id": 3,
        "chat_id": None,
        "user_id": 333,
        "text": "",
        "payload": {},
    }
    out = server._filter_updates([poll], ["222"], ["333"], ["poll_answer"], None)
    assert len(out) == 1


def test_filter_only_user_list_blocks_others():
    # 回歸：僅設 user 名單時，chat 未命中者不得因「chat 名單未設定」被放行
    items = [_msg(1, 999, 999), _msg(2, 999, 111)]
    out = server._filter_updates(items, [], ["111"], ["message"], None)
    assert [i["update_id"] for i in out] == [2]


def test_filter_only_chat_list_blocks_others():
    # 回歸：僅設 chat 名單時，chat 未命中者不得因「user 名單未設定」被放行
    items = [_msg(1, 999, 999), _msg(2, 222, 999)]
    out = server._filter_updates(items, ["222"], [], ["message"], None)
    assert [i["update_id"] for i in out] == [2]


def test_filter_poll_answer_unaffected_when_only_chat_list():
    # poll_answer 沒有 chat_id，僅設 chat 名單時不受其過濾
    poll = {
        "type": "poll_answer",
        "update_id": 3,
        "chat_id": None,
        "user_id": 999,
        "text": "",
        "payload": {},
    }
    out = server._filter_updates([poll], ["222"], [], ["poll_answer"], None)
    assert len(out) == 1


def test_filter_poll_answer_blocked_by_user_list():
    # 僅設 user 名單時，poll_answer 由 user_id 過濾
    poll = {
        "type": "poll_answer",
        "update_id": 3,
        "chat_id": None,
        "user_id": 999,
        "text": "",
        "payload": {},
    }
    assert server._filter_updates([poll], [], ["111"], ["poll_answer"], None) == []


# =====================================================================
# 前置檢查與 get_updates 入口行為（不觸網）
# =====================================================================


def test_validate_receive_env_priority_token_first(monkeypatch, no_whitelist):
    monkeypatch.setattr(server, "BOT_TOKEN", None)
    assert server._validate_receive_env() == server.MISSING_BOT_TOKEN


def test_validate_receive_env_missing_whitelist(fake_token, no_whitelist):
    assert server._validate_receive_env() == server.MISSING_ALLOWED_CHAT_IDS


def test_validate_receive_env_ok(fake_token, whitelisted):
    assert server._validate_receive_env() is None


def test_hint_mentions_env_var_and_both_tools():
    assert "TELEGRAM_ALLOWED_CHAT_IDS" in server.MISSING_ALLOWED_CHAT_IDS
    assert "get_updates" in server.MISSING_ALLOWED_CHAT_IDS
    assert "wait_for_reply" in server.MISSING_ALLOWED_CHAT_IDS


def test_get_updates_returns_setup_hint_without_whitelist(fake_token, no_whitelist):
    result = asyncio.run(server.get_updates())
    assert result == server.MISSING_ALLOWED_CHAT_IDS


def test_get_updates_returns_token_error(whitelisted, monkeypatch):
    monkeypatch.setattr(server, "BOT_TOKEN", None)
    result = asyncio.run(server.get_updates())
    assert "TELEGRAM_BOT_TOKEN" in result


# =====================================================================
# 工具註冊（走 FastMCP 公開 list_tools 介面）
# =====================================================================


def _registered_tool_names():
    async def _collect():
        tools = await server.mcp.list_tools()
        return {t.name for t in tools}

    return asyncio.run(_collect())


def test_receiving_tools_registered():
    names = _registered_tool_names()
    assert {"get_updates", "wait_for_reply", "answer_callback_query"} <= names


# =====================================================================
# get_updates offset 消耗語意（limit 分頁、無符合項清理、預覽模式）
# =====================================================================


def _raw_msg(update_id, chat_id=123456789, user_id=111, text="hi"):
    """組出 Telegram 原始 message update（_normalize_update 的輸入格式）。"""
    return {
        "update_id": update_id,
        "message": {
            "message_id": update_id,
            "chat": {"id": chat_id},
            "from": {"id": user_id},
            "text": text,
        },
    }


def test_get_updates_limit_truncation_preserves_remaining(
    state_dir, fake_token, whitelisted, monkeypatch
):
    # limit 截斷不得消耗未回傳的符合項目：offset 只推進到實際回傳最後一筆
    async def fake_once(offset, timeout_s, allowed_updates):
        if offset <= 1:
            return [_raw_msg(1), _raw_msg(2), _raw_msg(3)], None
        return [_raw_msg(3)], None  # 模擬 offset=3 時第 3 筆仍可取回

    monkeypatch.setattr(server, "_get_updates_once", fake_once)
    first = json.loads(asyncio.run(server.get_updates(limit=2)))
    assert [u["update_id"] for u in first["updates"]] == [1, 2]
    assert first["next_offset"] == 3

    second = json.loads(asyncio.run(server.get_updates(limit=2)))
    assert [u["update_id"] for u in second["updates"]] == [3]
    assert second["next_offset"] == 4
    assert server._load_offset() == 4


def test_get_updates_no_match_consumes_whole_batch(
    state_dir, fake_token, whitelisted, monkeypatch
):
    # 無符合項時整批消耗（含白名單外更新），避免積壓無限堆積
    async def fake_once(offset, timeout_s, allowed_updates):
        return [_raw_msg(9, chat_id=999)], None

    monkeypatch.setattr(server, "_get_updates_once", fake_once)
    result = asyncio.run(server.get_updates())
    assert "No pending updates" in result
    assert server._load_offset() == 10


def test_get_updates_mark_read_false_never_touches_offset(
    state_dir, fake_token, whitelisted, monkeypatch
):
    async def fake_once(offset, timeout_s, allowed_updates):
        return [_raw_msg(1), _raw_msg(2)], None

    monkeypatch.setattr(server, "_get_updates_once", fake_once)
    data = json.loads(asyncio.run(server.get_updates(mark_read=False)))
    assert data["next_offset"] == 0
    assert not (state_dir / "updates_state.json").exists()


# =====================================================================
# wait_for_reply 主流程與錯誤退避
# =====================================================================


def test_wait_for_reply_returns_match_and_persists_offset(
    state_dir, fake_token, whitelisted, monkeypatch
):
    async def fake_once(offset, timeout_s, allowed_updates):
        return [_raw_msg(7)], None

    monkeypatch.setattr(server, "_get_updates_once", fake_once)
    data = json.loads(asyncio.run(server.wait_for_reply(timeout=5)))
    assert data["count"] == 1
    assert data["updates"][0]["update_id"] == 7
    assert data["next_offset"] == 8
    assert server._load_offset() == 8


def test_wait_for_reply_backoff_clamped_to_one_second(
    state_dir, fake_token, whitelisted, monkeypatch
):
    # poll_interval<=0 時退避仍須至少 1 秒，不得形成緊密重試迴圈
    real_sleep = asyncio.sleep
    delays = []

    async def fake_sleep(delay, *args, **kwargs):
        delays.append(delay)
        await real_sleep(0)

    calls = []

    async def fake_once(offset, timeout_s, allowed_updates):
        calls.append(offset)
        if len(calls) <= 2:  # 前兩次網路錯誤，第三次出現匹配訊息以結束迴圈
            return [], "Connection Error (getUpdates): boom"
        return [_raw_msg(7)], None

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)
    monkeypatch.setattr(server, "_get_updates_once", fake_once)
    data = json.loads(asyncio.run(server.wait_for_reply(timeout=10, poll_interval=0)))
    assert data["updates"][0]["update_id"] == 7
    assert len(delays) == 2
    assert all(d >= 1 for d in delays)


def test_send_tools_registered():
    names = _registered_tool_names()
    assert {"send_text_message", "send_chat_action", "send_poll"} <= names


# =====================================================================
# answer_callback_query（mock _execute_post，不觸網）
# =====================================================================


@pytest.fixture()
def captured(monkeypatch):
    """攔截 _execute_post，記錄呼叫並回傳成功字串。"""
    calls = []

    async def fake_execute(endpoint, payload, files=None):
        calls.append((endpoint, payload))
        return "Success (answerCallbackQuery)"

    monkeypatch.setattr(server, "_execute_post", fake_execute)
    return calls


def test_answer_callback_query_payload(fake_token, captured):
    result = asyncio.run(server.answer_callback_query("cbq-1", text="OK"))
    assert result == "Success (answerCallbackQuery)"
    assert captured == [
        (
            "answerCallbackQuery",
            {
                "callback_query_id": "cbq-1",
                "show_alert": False,
                "cache_time": 0,
                "text": "OK",
            },
        )
    ]


def test_answer_callback_query_minimal_payload(fake_token, captured):
    asyncio.run(server.answer_callback_query("cbq-1"))
    assert captured[0][1] == {
        "callback_query_id": "cbq-1",
        "show_alert": False,
        "cache_time": 0,
    }


def test_answer_callback_query_url_and_cache_time(fake_token, captured):
    asyncio.run(
        server.answer_callback_query(
            "cbq-1", url="https://example.com", cache_time=60
        )
    )
    payload = captured[0][1]
    assert payload["url"] == "https://example.com"
    assert payload["cache_time"] == 60
    assert "text" not in payload


def test_answer_callback_query_show_alert_with_text(fake_token, captured):
    asyncio.run(server.answer_callback_query("cbq-1", text="注意", show_alert=True))
    assert captured[0][1]["show_alert"] is True
    assert captured[0][1]["text"] == "注意"


def test_answer_callback_query_empty_id_rejected(fake_token, captured):
    result = asyncio.run(server.answer_callback_query(""))
    assert "callback_query_id" in result
    assert captured == []


def test_answer_callback_query_blank_id_rejected(fake_token, captured):
    result = asyncio.run(server.answer_callback_query("   "))
    assert "callback_query_id" in result
    assert captured == []


def test_answer_callback_query_text_too_long_rejected(fake_token, captured):
    result = asyncio.run(server.answer_callback_query("cbq-1", text="a" * 201))
    assert "200" in result
    assert captured == []


def test_answer_callback_query_show_alert_without_text_rejected(fake_token, captured):
    result = asyncio.run(server.answer_callback_query("cbq-1", show_alert=True))
    assert "show_alert" in result
    assert captured == []


def test_answer_callback_query_text_and_url_mutually_exclusive(fake_token, captured):
    result = asyncio.run(
        server.answer_callback_query("cbq-1", text="OK", url="https://example.com")
    )
    assert "mutually exclusive" in result
    assert captured == []


def test_answer_callback_query_invalid_url_rejected(fake_token, captured):
    result = asyncio.run(server.answer_callback_query("cbq-1", url="ftp://x"))
    assert "http" in result
    assert captured == []


def test_answer_callback_query_cache_time_out_of_range_rejected(fake_token, captured):
    result = asyncio.run(server.answer_callback_query("cbq-1", cache_time=604801))
    assert "cache_time" in result
    assert captured == []
    result = asyncio.run(server.answer_callback_query("cbq-1", cache_time=-1))
    assert "cache_time" in result
    assert captured == []


def test_answer_callback_query_missing_token(monkeypatch, captured):
    monkeypatch.setattr(server, "BOT_TOKEN", None)
    result = asyncio.run(server.answer_callback_query("cbq-1"))
    assert result == server.MISSING_BOT_TOKEN
    assert captured == []


def test_answer_callback_query_forwards_telegram_error(fake_token, monkeypatch):
    async def fake_error(endpoint, payload, files=None):
        return "Telegram API Error (answerCallbackQuery): query is too old"

    monkeypatch.setattr(server, "_execute_post", fake_error)
    result = asyncio.run(server.answer_callback_query("cbq-1"))
    assert "query is too old" in result


# =====================================================================
# 自動應答（auto_answer：callback_query 取回當下立即應答）
# =====================================================================


@pytest.fixture()
def answered(monkeypatch):
    """攔截 _post_answer_callback，記錄呼叫並回傳成功字串。"""
    calls = []

    async def fake_post(cb_id, text=""):
        calls.append((cb_id, text))
        return "Success (answerCallbackQuery)"

    monkeypatch.setattr(server, "_post_answer_callback", fake_post)
    return calls


def _raw_cb(update_id, cb_id="cbq-1", data="action=ok"):
    """組出 Telegram 原始 callback_query update（_normalize_update 的輸入格式）。"""
    return {
        "update_id": update_id,
        "callback_query": {
            "id": cb_id,
            "data": data,
            "from": {"id": 111},
            "message": {"message_id": 20, "chat": {"id": 123456789}},
        },
    }


def test_get_updates_auto_answers_callback_by_default(
    state_dir, fake_token, whitelisted, monkeypatch, answered
):
    async def fake_once(offset, timeout_s, allowed_updates):
        return [_raw_cb(1)], None

    monkeypatch.setattr(server, "_get_updates_once", fake_once)
    data = json.loads(asyncio.run(server.get_updates()))
    assert data["updates"][0]["payload"]["auto_answered"] is True
    assert answered == [("cbq-1", server.AUTO_ANSWER_TEXT)]
    assert server._load_offset() == 2


def test_get_updates_auto_answer_disabled_skips_answer(
    state_dir, fake_token, whitelisted, monkeypatch, answered
):
    async def fake_once(offset, timeout_s, allowed_updates):
        return [_raw_cb(1)], None

    monkeypatch.setattr(server, "_get_updates_once", fake_once)
    data = json.loads(asyncio.run(server.get_updates(auto_answer=False)))
    assert "auto_answered" not in data["updates"][0]["payload"]
    assert answered == []


def test_get_updates_preview_mode_never_auto_answers(
    state_dir, fake_token, whitelisted, monkeypatch, answered
):
    # 預覽模式不得有任何副作用（含應答），否則重複預覽會重複應答
    async def fake_once(offset, timeout_s, allowed_updates):
        return [_raw_cb(1)], None

    monkeypatch.setattr(server, "_get_updates_once", fake_once)
    asyncio.run(server.get_updates(mark_read=False))
    assert answered == []


def test_get_updates_auto_answer_error_does_not_block_updates(
    state_dir, fake_token, whitelisted, monkeypatch
):
    async def failing_post(cb_id, text=""):
        return "Telegram API Error (answerCallbackQuery): Bad Request: query is too old"

    monkeypatch.setattr(server, "_post_answer_callback", failing_post)

    async def fake_once(offset, timeout_s, allowed_updates):
        return [_raw_cb(1)], None

    monkeypatch.setattr(server, "_get_updates_once", fake_once)
    data = json.loads(asyncio.run(server.get_updates()))
    payload = data["updates"][0]["payload"]
    assert "query is too old" in payload["auto_answer_error"]
    assert "auto_answered" not in payload
    assert data["updates"][0]["text"] == "action=ok"


def test_wait_for_reply_auto_answers_callback(
    state_dir, fake_token, whitelisted, monkeypatch, answered
):
    async def fake_once(offset, timeout_s, allowed_updates):
        return [_raw_cb(7)], None

    monkeypatch.setattr(server, "_get_updates_once", fake_once)
    data = json.loads(asyncio.run(server.wait_for_reply(timeout=5)))
    assert data["updates"][0]["payload"]["auto_answered"] is True
    assert answered == [("cbq-1", server.AUTO_ANSWER_TEXT)]
    assert server._load_offset() == 8


def test_wait_for_reply_auto_answer_disabled_skips_answer(
    state_dir, fake_token, whitelisted, monkeypatch, answered
):
    async def fake_once(offset, timeout_s, allowed_updates):
        return [_raw_cb(7)], None

    monkeypatch.setattr(server, "_get_updates_once", fake_once)
    data = json.loads(asyncio.run(server.wait_for_reply(timeout=5, auto_answer=False)))
    assert "auto_answered" not in data["updates"][0]["payload"]
    assert answered == []


def test_auto_answer_skips_non_callback_and_missing_id(answered):
    asyncio.run(
        server._auto_answer_callbacks(
            [
                {"type": "message", "update_id": 1, "payload": {}},
                {"type": "callback_query", "update_id": 2, "payload": {}},
            ]
        )
    )
    assert answered == []


def test_auto_answer_exception_is_recorded_not_raised(monkeypatch):
    async def raising_post(cb_id, text=""):
        raise RuntimeError("network down")

    monkeypatch.setattr(server, "_post_answer_callback", raising_post)
    items = [
        {
            "type": "callback_query",
            "update_id": 1,
            "payload": {"callback_query_id": "cbq-9"},
        }
    ]
    asyncio.run(server._auto_answer_callbacks(items))
    assert items[0]["payload"]["auto_answer_error"] == "network down"
