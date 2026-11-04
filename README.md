# mcp-telegram-agent

A lightweight, zero-login-risk Model Context Protocol (MCP) server empowering AI agents with Telegram Bot capabilities. Built with Python (SDK-compatible with both `mcp` 1.x FastMCP and 2.x MCPServer), designed to work seamlessly out-of-the-box with `uvx` and modern AI coding agents like VS Code Cline and Claude Desktop.

Also includes the ultra-short command alias `tg-agent`.

[繁體中文說明文件](README.zh-TW.md)

---

## Highlights

* **Pure Bot API Architecture**: Zero login session risk, no SMS codes or sensitive credential files needed.
* **Dual CLI Entry Points**: Call via standard `mcp-telegram-agent` or the compact `tg-agent` alias.
* **Full Keyboard Support**: Effortlessly construct dynamic Inline Keyboards (with URLs or callback data) and custom Reply Keyboards.
* **Rich Media & Local Files**: Deliver logs, reports, source code, images, audio, voice notes, videos, and multi-image albums (2–10 files).
* **Interactive Tooling**: Launch quizzes, single/multiple-choice polls, GPS coordinates, digital contact cards, and animated dice.
* **Message Lifecycle**: Broadcast bot statuses (typing, uploading) and edit or delete messages on the fly.
* **Instant uvx Execution**: Run directly with no virtual environments or manual package installs.

---

## Quick Start

### 1. Prerequisites
* **Telegram Bot Token**: Obtain one from `@BotFather`.
* **Chat ID**: Get your unique numerical Chat ID by sending any message to `@userinfobot`.

### 2. Configuration for AI Clients

Add the configuration below to your MCP settings file (e.g., `cline_mcp_settings.json` or `claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "Telegram": {
      "command": "uvx",
      "args": ["mcp-telegram-agent"],
      "env": {
        "TELEGRAM_BOT_TOKEN": "YOUR_TELEGRAM_BOT_TOKEN",
        "TELEGRAM_DEFAULT_CHAT_ID": "YOUR_CHAT_ID"
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

> **Note on `autoApprove`**: This field is specific to VS Code Cline (`cline_mcp_settings.json`). It whitelists all 13 tools so the agent can send messages without asking for confirmation each time. Claude Desktop does not support `autoApprove` — simply remove this field when using `claude_desktop_config.json`. Only add `autoApprove` if you fully trust the bot's target chat, as the agent will be able to send messages autonomously.

---

## Available Tools

* `send_text_message`: Send Markdown/HTML text with inline buttons or custom reply keyboards.
* `send_local_document`: Send any local file (PDF, CSV, code, logs, archives).
* `send_local_photo`: Send image files with captions and inline buttons.
* `send_local_video`: Send video files as native players.
* `send_local_audio_or_voice`: Send music tracks or native voice audio notes.
* `send_media_album`: Deliver 2 to 10 photos or videos as a grouped carousel.
* `send_poll`: Create interactive single/multiple choice polls or scored quizzes.
* `send_location`: Broadcast map location points via coordinates.
* `send_contact`: Share phone contact cards.
* `send_dice`: Send animated dice, basketball, football, or slot machines.
* `send_chat_action`: Display temporary bot statuses (typing, uploading).
* `edit_message_text`: Dynamically update previously sent text and keyboards.
* `delete_message`: Clean up or remove specific messages.

---

## License

This project is licensed under the MIT License.

