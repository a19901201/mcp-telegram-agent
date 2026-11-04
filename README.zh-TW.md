# mcp-telegram-agent

專為 AI 代理與自動化流程設計的全功能 Telegram 機器人控制協議伺服器。採用純 Python 實作，相容 mcp SDK 1.x（FastMCP）與 2.x（MCPServer），原生支援 `uvx` 隨選即用，完美相容 VS Code Cline 與 Claude Desktop 等開發環境。

同時支援超短指令別名 `tg-agent`。

[English Documentation](README.md)

---

## 專案亮點

* **純機器人架構**：僅需 Bot Token 與 Chat ID，無需輸入電話驗證碼登入個人帳號，零帳號被封風險。
* **雙命令列進入點**：同時支援標準 `mcp-telegram-agent` 與精簡 `tg-agent` 別名指令。
* **完整鍵盤支援**：原生支援行內按鈕（超連結與回傳識別碼）以及手機底部回覆鍵盤。
* **實體本機檔案與相簿**：輕鬆發送日誌、報表、原始碼、圖片、語音、影片，以及 2 至 10 個項目的多媒體相簿。
* **豐富互動元件**：支援即時投票、測驗、地圖經緯度座標、電話名片及官方動畫表情符號。
* **狀態與訊息生命週期維護**：支援即時廣播機器人打字狀態，並能動態更新或刪除指定訊息。
* **uvx 極速啟動**：免除手動建立虛擬環境與安裝依賴的繁瑣步驟。

---

## 快速開始

### 1. 前置準備
* **Telegram Bot Token**：於 Telegram 搜尋 `@BotFather` 建立機器人並獲取 Token。
* **Chat ID**：發送任一訊息給 `@userinfobot` 獲取個人專屬數值 Chat ID。

### 2. 用戶端配置範例

在 MCP 設定檔（例如 VS Code 的 `cline_mcp_settings.json` 或 `claude_desktop_config.json`）中加入以下內容：

```json
{
  "mcpServers": {
    "Telegram": {
      "command": "uvx",
      "args": ["mcp-telegram-agent"],
      "env": {
        "TELEGRAM_BOT_TOKEN": "你的_BOT_TOKEN",
        "TELEGRAM_DEFAULT_CHAT_ID": "你的_CHAT_ID"
      },
      "autoApprove": [
        "send_text_message",
        "send_chat_action",
        "send_local_document",
        "send_local_photo",
        "send_local_video",
        "send_local_audio_or_voice",
        "send_media_album",
        "send_poll",
        "send_location",
        "send_contact",
        "send_dice",
        "edit_message_text",
        "delete_message"
      ]
    }
  }
}
```

> **`autoApprove` 說明**：此欄位為 VS Code Cline 專用（`cline_mcp_settings.json`），將全部 13 個工具列入白名單，讓 AI 代理發送訊息時免每次人工確認。Claude Desktop 不支援此欄位，使用 `claude_desktop_config.json` 時請移除。請僅在完全信任目標聊天對象時開啟自動核准，AI 代理將能自主發送訊息。

---

## 提供之工具列表

* `send_text_message`：發送 Markdown 與 HTML 格式化文字，支援行內按鈕或底部鍵盤。
* `send_local_document`：傳送各類本機報告、CSV、ZIP 或原始碼檔案。
* `send_local_photo`：發送圖片檔案並支援即時全螢幕預覽。
* `send_local_video`：發送本機影片並支援內嵌播放器。
* `send_local_audio_or_voice`：發送音訊或語音留言。
* `send_media_album`：批次發送 2 至 10 張圖片或影片組成相簿輪播。
* `send_poll`：建立互動式單選、多選投票或附帶解析之標準測驗。
* `send_location`：傳送經緯度地理位置座標地圖。
* `send_contact`：傳送名片聯絡人資訊。
* `send_dice`：發送隨機動畫表情，如骰子與拉霸機等。
* `send_chat_action`：向用戶端顯示當前操作狀態，如打字中與上傳檔案中。
* `edit_message_text`：動態更新既有訊息內容與按鈕。
* `delete_message`：清理特定暫存或歷史訊息。

---

## 授權條款

本專案採用 MIT 授權協議開源發布。
