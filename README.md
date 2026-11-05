<div align="center">

# 📬 mcp-telegram-agent

**Give your AI agent full Telegram Bot superpowers — zero login risk, zero setup.**

A Model Context Protocol (MCP) server empowering AI agents with Telegram Bot capabilities. Built with Python (SDK-compatible with both `mcp` 1.x FastMCP and 2.x MCPServer), designed to work seamlessly out-of-the-box with `uvx` and modern AI coding agents like VS Code Cline and Claude Desktop. Also includes the ultra-short command alias `tg-agent`.

[![PyPI Version](https://img.shields.io/pypi/v/mcp-telegram-agent?color=blue&logo=pypi)](https://pypi.org/project/mcp-telegram-agent/)
[![Python Versions](https://img.shields.io/pypi/pyversions/mcp-telegram-agent?logo=python)](https://pypi.org/project/mcp-telegram-agent/)
[![PyPI Downloads](https://img.shields.io/pypi/dm/mcp-telegram-agent?color=green)](https://pypi.org/project/mcp-telegram-agent/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**English** · [繁體中文](README.zh-TW.md) · [简体中文](README.zh-CN.md)

</div>

> 🔐 **Stop giving AI your personal Telegram account credentials.**
>
> **mcp-telegram-agent** is a lightweight, zero-login-risk notification and delivery tool — just one Bot Token sends local files, reports, interactive keyboards, and rich notifications straight to your phone.

---

## ✨ Highlights

* **Pure Bot API Architecture** — Zero login session risk, no SMS codes or sensitive credential files needed.
* **Dual CLI Entry Points** — Call via standard `mcp-telegram-agent` or the compact `tg-agent` alias.
* **Full Keyboard Support** — Effortlessly construct dynamic Inline Keyboards (with URLs or callback data) and custom Reply Keyboards.
* **Rich Media & Local Files** — Deliver logs, reports, source code, images, audio, voice notes, videos, and multi-image albums (2–10 files).
* **Interactive Tooling** — Launch quizzes, single/multiple-choice polls, GPS coordinates, digital contact cards, and animated dice.
* **Message Lifecycle** — Broadcast bot statuses (typing, uploading) and edit or delete messages on the fly.
* **Instant uvx Execution** — Run directly with no virtual environments or manual package installs.

---

## 🚀 Quick Start

### 1️⃣ Create a Telegram Bot & Get the Token

1. Open Telegram and search for **@BotFather** (verified blue check).
2. Send `/newbot` and follow the prompts: choose a display name, then a username ending in `bot` (e.g. `my_alert_bot`).
3. BotFather replies with your **Bot Token**, e.g. `123456789:AAHxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`. Keep it secret — anyone with this token can control your bot.
4. **Important**: open your new bot's chat and press **Start** (or send `/start`). A bot cannot message a user who has never started a conversation with it.

### 2️⃣ Get Your Personal Chat ID

1. Send any message (e.g. "hi") to your new bot.
2. Open this URL in a browser, replacing `<YOUR_BOT_TOKEN>` with your token:
   `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
3. In the JSON response, locate `"chat":{"id": 123456789, ...}` — that number is your **Chat ID**.
   * Alternative: send any message to `@userinfobot` and it replies with your ID.

### 3️⃣ Send to Groups or Channels (Optional)

* **Add the bot to the group** first (via group settings → *Add members*). For channels, the bot must be added as an **administrator** to post.
* **Group IDs are negative numbers** (e.g. `-1001234567890`). To find one:
  * Temporarily add `@userinfobot` to the group and forward a group message to it, **or**
  * Disable the bot's *Group Privacy* via @BotFather (`/setprivacy` → select your bot → *Disable*), post a message in the group, then check `getUpdates` as above.
* Once the bot is a member of the group/channel, it can send messages there — no extra configuration needed.

### 4️⃣ Sending to Any Chat at Runtime

`TELEGRAM_DEFAULT_CHAT_ID` is only the **fallback target**. Every tool accepts an optional `chat_id` parameter, so you can simply ask your AI agent to *"send this to chat ID -1001234567890"*:

* `chat_id` **omitted** → the message goes to the `TELEGRAM_DEFAULT_CHAT_ID` from your config.
* `chat_id` **provided** → the message goes to that user/group/channel instead.
* Requirement: the bot must be a member of that group/channel (or the target user must have pressed Start on the bot).

### 5️⃣ Configuration for AI Clients

Add the configuration below to your MCP settings file (e.g., `cline_mcp_settings.json` or `claude_desktop_config.json`).

#### ✅ Example A — Universal Default (Recommended)

A universal configuration that works with **every** MCP client — just fill in your bot token and chat ID:

```json
{
  "mcpServers": {
    "Telegram": {
      "command": "uvx",
      "args": ["mcp-telegram-agent"],
      "env": {
        "TELEGRAM_BOT_TOKEN": "YOUR_TELEGRAM_BOT_TOKEN",
        "TELEGRAM_DEFAULT_CHAT_ID": "YOUR_CHAT_ID"
      }
    }
  }
}
```

> 💡 **Both `env` variables are optional.** If they are missing, the server still starts normally — it returns a clear, human-readable error only when a tool call actually needs the token or the fallback chat ID. This also allows a credential-free trial run with no `env` block at all:

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

## 🧰 Available Tools

| Tool | Description |
| --- | --- |
| `send_text_message` | Send Markdown/HTML text with inline buttons or custom reply keyboards. |
| `send_local_document` | Send any local file (PDF, CSV, code, logs, archives). |
| `send_local_photo` | Send image files with captions and inline buttons. |
| `send_local_video` | Send video files as native players. |
| `send_local_audio_or_voice` | Send music tracks or native voice audio notes. |
| `send_media_album` | Deliver 2 to 10 photos or videos as a grouped carousel. |
| `send_poll` | Create interactive single/multiple choice polls or scored quizzes. |
| `send_location` | Broadcast map location points via coordinates. |
| `send_contact` | Share phone contact cards. |
| `send_dice` | Send animated dice, basketball, football, or slot machines. |
| `send_chat_action` | Display temporary bot statuses (typing, uploading). |
| `edit_message_text` | Dynamically update previously sent text and keyboards. |
| `delete_message` | Clean up or remove specific messages. |

---

## 💬 Usage Examples

Once configured, simply talk to your AI agent in natural language — it picks the right tool automatically. Below are typical requests together with the tool calls the agent makes:

### 📢 Send a formatted notification

> "Tell me in Telegram that the nightly build succeeded, with a button linking to https://example.com"

```json
{
  "tool": "send_text_message",
  "arguments": {
    "text": "✅ *Nightly build succeeded!*",
    "parse_mode": "Markdown",
    "inline_buttons": [[{"text": "Dashboard", "url": "https://example.com"}]]
  }
}
```

### 📁 Share local files

> "Upload `logs/app.log` to my Telegram and summarize the errors"

```json
{
  "tool": "send_local_document",
  "arguments": {
    "file_path": "logs/app.log",
    "caption": "Error log summary: 3 timeout warnings"
  }
}
```

### 🖼️ Send an album

> "Send the three screenshots in `screenshots/` to my Telegram as one album"

```json
{
  "tool": "send_media_album",
  "arguments": {
    "file_paths": ["screenshots/1.png", "screenshots/2.png", "screenshots/3.png"],
    "caption": "Latest UI screenshots"
  }
}
```

### 🗳️ Run a quiz in a group

> "Post a quiz to chat ID -1001234567890: which port does HTTPS use? Options 80 / 443 / 8080, the answer is 443, with a short explanation"

```json
{
  "tool": "send_poll",
  "arguments": {
    "chat_id": "-1001234567890",
    "question": "Which port does HTTPS use?",
    "options": ["80", "443", "8080"],
    "type": "quiz",
    "correct_option_id": 1,
    "explanation": "HTTPS defaults to port 443."
  }
}
```

### ♻️ Update or clean up messages

> "Change that deployment notice to 'finished', then delete the old reminder (ID 120)"

```json
{
  "tool": "edit_message_text",
  "arguments": { "message_id": 123, "text": "🚀 Deployment **finished**" }
}
```

```json
{
  "tool": "delete_message",
  "arguments": { "message_id": 120 }
}
```

> 💡 When `chat_id` is omitted, messages go to `TELEGRAM_DEFAULT_CHAT_ID`; pass it explicitly to reach any user, group, or channel — see step 4️⃣ above.

---

## 🛠️ Development & Release Flow

* Develop against **`main`** — all feature work and PRs land here.
* Publishing happens **only** from the **`release`** branch: open a PR `main` → `release`, bump `version` in `pyproject.toml` within the PR, then merge — CI builds and publishes to PyPI automatically, and creates a matching GitHub Release (`v*` tag + auto-generated notes).
* If the version was not bumped, the workflow skips publishing with a clear warning — docs-only PRs won't break CI.
* Direct pushes to `release` are blocked by branch protection; always go through a PR.

---

## 📄 License

This project is licensed under the MIT License.

