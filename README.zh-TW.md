<div align="center">

# 📬 mcp-telegram-agent

**讓你的 AI 代理直接擁有 Telegram 機器人的全部能力——零登入風險、零環境設定。**

專為 AI 代理與自動化流程設計的全功能 Telegram 機器人控制協議（MCP）伺服器。採用純 Python 實作，相容 mcp SDK 1.x（FastMCP）與 2.x（MCPServer），原生支援 `uvx` 隨選即用，完美相容 VS Code Cline、Claude Desktop 等開發環境。同時支援超短指令別名 `tg-agent`。

[![PyPI Version](https://img.shields.io/pypi/v/mcp-telegram-agent?color=blue&logo=pypi)](https://pypi.org/project/mcp-telegram-agent/)
[![Python Versions](https://img.shields.io/pypi/pyversions/mcp-telegram-agent?logo=python)](https://pypi.org/project/mcp-telegram-agent/)
[![PyPI Downloads](https://img.shields.io/pypi/dm/mcp-telegram-agent?color=green)](https://pypi.org/project/mcp-telegram-agent/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

[English](README.md) · **繁體中文** · [简体中文](README.zh-CN.md)

</div>

---

## ✨ 專案亮點

* **純機器人架構** — 僅需 Bot Token 與 Chat ID，無需輸入電話驗證碼登入個人帳號，零帳號被封風險。
* **雙命令列進入點** — 同時支援標準 `mcp-telegram-agent` 與精簡 `tg-agent` 別名指令。
* **完整鍵盤支援** — 原生支援行內按鈕（超連結與回傳識別碼）以及手機底部回覆鍵盤。
* **實體本機檔案與相簿** — 輕鬆發送日誌、報表、原始碼、圖片、語音、影片，以及 2 至 10 個項目的多媒體相簿。
* **豐富互動元件** — 支援即時投票、測驗、地圖經緯度座標、電話名片及官方動畫表情符號。
* **狀態與訊息生命週期維護** — 支援即時廣播機器人打字狀態，並能動態更新或刪除指定訊息。
* **uvx 極速啟動** — 免除手動建立虛擬環境與安裝依賴的繁瑣步驟。

---

## 🚀 快速開始

### 1️⃣ 申請 Telegram 機器人並取得 Token

1. 開啟 Telegram 搜尋 **@BotFather**（有藍色勾勾認證）。
2. 傳送 `/newbot`，依提示輸入顯示名稱，再取一個以 `bot` 結尾的帳號名（如 `my_alert_bot`）。
3. BotFather 會回覆你的 **Bot Token**，格式如 `123456789:AAHxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`。請妥善保管——取得此 Token 的人就能完全控制你的機器人。
4. **重要**：開啟新機器人的聊天視窗按下 **Start**（或傳送 `/start`）。使用者若從未與機器人開啟對話，機器人是無法主動傳訊給他的。

### 2️⃣ 取得個人 Chat ID

1. 傳送任一訊息（如「hi」）給你的新機器人。
2. 用瀏覽器開啟下列網址，將 `<YOUR_BOT_TOKEN>` 換成你的 Token：
   `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
3. 在回傳的 JSON 中找到 `"chat":{"id": 123456789, ...}`，該數值即是你的 **Chat ID**。
   * 替代做法：傳送任一訊息給 `@userinfobot`，它會直接回覆你的 ID。

### 3️⃣ 發送到群組或頻道（選用）

* 先**把機器人加入群組**（群組設定 → 加入成員）。頻道則須將機器人設為**管理員**才能發文。
* **群組 ID 為負數**（如 `-1001234567890`）。取得方式：
  * 暫時把 `@userinfobot` 拉進群組，轉發一則群組訊息給它即可查得；**或**
  * 先在 @BotFather 執行 `/setprivacy` → 選擇你的機器人 → **Disable**（關閉隱私模式），在群組內發一則訊息後，再以 `getUpdates` 查詢。
* 機器人一旦成為群組／頻道成員，即可直接發送訊息，無需額外設定。

### 4️⃣ 執行時發送到任意 Chat

`TELEGRAM_DEFAULT_CHAT_ID` 只是**預設收件人**。所有工具都接受選用的 `chat_id` 參數，你可以直接對 AI 代理說「把這則訊息發到 chat ID -1001234567890」：

* **未提供** `chat_id` → 訊息送到設定檔中的 `TELEGRAM_DEFAULT_CHAT_ID`。
* **有提供** `chat_id` → 訊息改送到指定的使用者／群組／頻道。
* 前提：機器人必須已在該群組／頻道內（或該使用者已對機器人按過 Start）。

### 5️⃣ 用戶端配置範例

在 MCP 設定檔（例如 VS Code 的 `cline_mcp_settings.json` 或 `claude_desktop_config.json`）中加入以下內容。

#### ✅ 範例 A — 通用預設配置（建議）

適用於**所有** MCP 用戶端的通用配置——只需填入你的權杖與 chat_id：

```json
{
  "mcpServers": {
    "Telegram": {
      "command": "uvx",
      "args": ["mcp-telegram-agent"],
      "env": {
        "TELEGRAM_BOT_TOKEN": "你的_BOT_TOKEN",
        "TELEGRAM_DEFAULT_CHAT_ID": "你的_CHAT_ID"
      }
    }
  }
}
```

> 💡 **兩個環境變數皆為選填。** 缺少任一變數時伺服器仍會正常啟動，只在實際呼叫需要權杖或預設 chat_id 的工具時，回傳清楚的錯誤說明。也可以整段省略 `env` 區塊，進行不帶憑證的試運行：

```json
{
  "mcpServers": {
    "Telegram": {
      "command": "uvx",
      "args": ["mcp-telegram-agent"]
    }
  }
}
```

---

## 🧰 提供之工具列表

| 工具 | 說明 |
| --- | --- |
| `send_text_message` | 發送 Markdown 與 HTML 格式化文字，支援行內按鈕或底部鍵盤。 |
| `send_local_document` | 傳送各類本機報告、CSV、ZIP 或原始碼檔案。 |
| `send_local_photo` | 發送圖片檔案並支援即時全螢幕預覽。 |
| `send_local_video` | 發送本機影片並支援內嵌播放器。 |
| `send_local_audio_or_voice` | 發送音訊或語音留言。 |
| `send_media_album` | 批次發送 2 至 10 張圖片或影片組成相簿輪播。 |
| `send_poll` | 建立互動式單選、多選投票或附帶解析之標準測驗。 |
| `send_location` | 傳送經緯度地理位置座標地圖。 |
| `send_contact` | 傳送名片聯絡人資訊。 |
| `send_dice` | 發送隨機動畫表情，如骰子與拉霸機等。 |
| `send_chat_action` | 向用戶端顯示當前操作狀態，如打字中與上傳檔案中。 |
| `edit_message_text` | 動態更新既有訊息內容與按鈕。 |
| `delete_message` | 清理特定暫存或歷史訊息。 |

---

## 💬 使用範例

完成配置後，直接用自然語言對 AI 代理下指令，代理會自動挑選合適的工具。以下列出常見指令與代理實際呼叫的工具參數：

### 📢 發送格式化通知

> 「在 Telegram 通知我今晚的建置成功了，並附上一個連到 https://example.com 的按鈕」

```json
{
  "tool": "send_text_message",
  "arguments": {
    "text": "✅ *今晚建置成功！*",
    "parse_mode": "Markdown",
    "inline_buttons": [[{"text": "儀表板", "url": "https://example.com"}]]
  }
}
```

### 📁 傳送本機檔案

> 「把 `logs/app.log` 傳到我的 Telegram，並摘要錯誤內容」

```json
{
  "tool": "send_local_document",
  "arguments": {
    "file_path": "logs/app.log",
    "caption": "錯誤日誌摘要：3 次逾時警告"
  }
}
```

### 🖼️ 發送相簿

> 「把 `screenshots/` 裡的三張截圖以一則相簿傳到我的 Telegram」

```json
{
  "tool": "send_media_album",
  "arguments": {
    "file_paths": ["screenshots/1.png", "screenshots/2.png", "screenshots/3.png"],
    "caption": "最新 UI 截圖"
  }
}
```

### 🗳️ 在群組發起測驗

> 「在 chat ID -1001234567890 發一則測驗：HTTPS 使用哪個連接埠？選項 80／443／8080，正解 443，並附簡短解析」

```json
{
  "tool": "send_poll",
  "arguments": {
    "chat_id": "-1001234567890",
    "question": "HTTPS 使用哪個連接埠？",
    "options": ["80", "443", "8080"],
    "type": "quiz",
    "correct_option_id": 1,
    "explanation": "HTTPS 預設使用連接埠 443。"
  }
}
```

### ♻️ 更新或清理訊息

> 「把那則部署通知改成『已完成』，然後刪除舊的提醒（ID 120）」

```json
{
  "tool": "edit_message_text",
  "arguments": { "message_id": 123, "text": "🚀 部署**已完成**" }
}
```

```json
{
  "tool": "delete_message",
  "arguments": { "message_id": 120 }
}
```

> 💡 未提供 `chat_id` 時，訊息送到 `TELEGRAM_DEFAULT_CHAT_ID`；明確傳入 `chat_id` 即可發送給任何使用者、群組或頻道——見上方第 4️⃣ 步。

---

## 🛠️ 開發與發布流程

* 功能開發一律先進 **`main`** 分支（PR 合併至 main）。
* 發布**僅**透過 **`release`** 分支：自 `main` 建立 PR 指向 `release`，在 PR 中調升 `pyproject.toml` 的 `version` 後合併，CI 即自動建置並發布至 PyPI，同時自動建立對應的 GitHub Release（`v*` 標籤與自動生成的 release notes）。
* 若未調升版本，workflow 會明確警告並跳過發布——純文件 PR 不會讓 CI 失敗。
* `release` 分支已啟用分支保護，禁止直接 push，一律經 PR 發布。

---

## 📄 授權條款

本專案採用 MIT 授權協議開源發布。
