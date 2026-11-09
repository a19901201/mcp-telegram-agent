"""發送工具（send_text_message / send_chat_action）基本單元測試。"""

import asyncio

import pytest

import mcp_telegram_agent.server as server


@pytest.fixture(autouse=True)
def _no_default_chat_id(monkeypatch):
    """確保模組常數缺席，測試不依賴外部環境設定。"""
    monkeypatch.setattr(server, "DEFAULT_CHAT_ID", None)


def test_send_text_message_missing_chat_id():
    result = asyncio.run(server.send_text_message("hello", chat_id=""))
    assert result == server.MISSING_CHAT_ID


def test_send_chat_action_missing_chat_id():
    result = asyncio.run(server.send_chat_action("typing", chat_id=""))
    assert result == server.MISSING_CHAT_ID


def test_build_reply_markup_inline_buttons():
    import json

    buttons = [[server.InlineButton(text="刪除", callback_data="action=delete")]]
    markup = server._build_reply_markup(inline_buttons=buttons)
    data = json.loads(markup)
    assert data["inline_keyboard"][0][0]["text"] == "刪除"
    assert data["inline_keyboard"][0][0]["callback_data"] == "action=delete"


def test_build_reply_markup_reply_keyboard():
    markup = server._build_reply_markup(reply_keyboard=[["確認", "取消"]])
    assert '"keyboard"' in markup
    assert '"one_time_keyboard":true' in markup.replace(" ", "")


def test_build_reply_markup_remove_keyboard():
    markup = server._build_reply_markup(remove_keyboard=True)
    assert '"remove_keyboard":true' in markup.replace(" ", "")