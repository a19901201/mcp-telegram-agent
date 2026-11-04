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

### 1. 申請 Telegram 機器人並取得 Token

1. 開啟 Telegram 搜尋 **@BotFather**（有藍色勾勾認證）。
2. 傳送 `/newbot`，依提示輸入顯示名稱，再取一個以 `bot` 結尾的帳號名（如 `my_alert_bot`）。
3. BotFather 會回覆你的 **Bot Token**，格式如 `123456789:AAHxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`。請妥善保管——取得此 Token 的人就能完全控制你的機器人。
4. **重要**：開啟新機器人的聊天視窗按下 **Start**（或傳送 `/start`）。使用者若從未與機器人開啟對話，機器人是無法主動傳訊給他的。

### 2. 取得個人 Chat ID

1. 傳送任一訊息（如「hi」）給你的新機器人。
2. 用瀏覽器開啟下列網址，將 `<YOUR_BOT_TOKEN>` 換成你的 Token：
   `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
3. 在回傳的 JSON 中找到 `"chat":{"id": 123456789, ...}`，該數值即是你的 **Chat ID**。
   * 替代做法：傳送任一訊息給 `@userinfobot`，它會直接回覆你的 ID。

### 3. 發送到群組或頻道（選用）

* 先**把機器人加入群組**（群組設定 → 加入成員）。頻道則須將機器人設為**管理員**才能發文。
* **群組 ID 為負數**（如 `-1001234567890`）。取得方式：
  * 暫時把 `@userinfobot` 拉進群組，轉發一則群組訊息給它即可查得；**或**
  * 先在 @BotFather 執行 `/setprivacy` → 選擇你的機器人 → **Disable**（關閉隱私模式），在群組內發一則訊息後，再以 `getUpdates` 查詢。
* 機器人一旦成為群組／頻道成員，即可直接發送訊息，無需額外設定。

### 4. 執行時發送到任意 Chat

`TELEGRAM_DEFAULT_CHAT_ID` 只是**預設收件人**。所有工具都接受選用的 `chat_id` 參數，你可以直接對 AI 代理說「把這則訊息發到 chat ID -1001234567890」：

* **未提供** `chat_id` → 訊息送到設定檔中的 `TELEGRAM_DEFAULT_CHAT_ID`。
* **有提供** `chat_id` → 訊息改送到指定的使用者／群組／頻道。
* 前提：機器人必須已在該群組／頻道內（或該使用者已對機器人按過 Start）。

### 5. 用戶端配置範例

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

## 開發與發布流程

* 功能開發一律先進 **`main`** 分支（PR 合併至 main）。
* 發布**僅**透過 **`release`** 分支：自 `main` 建立 PR 指向 `release`，在 PR 中調升 `pyproject.toml` 的 `version` 後合併，CI 即自動建置並發布至 PyPI；若未調升版本，守門步驟會直接判失敗。
* `release` 分支已啟用分支保護，禁止直接 push，一律經 PR 發布。

---

## 授權條款

本專案採用 MIT 授權協議開源發布。
