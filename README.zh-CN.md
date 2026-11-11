<div align="center">

# 📬 mcp-telegram-agent

**让你的 AI 代理直接拥有 Telegram 机器人的全部能力——零登录风险、零环境配置。**

专为 AI 代理与自动化流程设计的全功能 Telegram 机器人控制协议（MCP）服务器。采用纯 Python 实现，兼容 mcp SDK 1.x（FastMCP）与 2.x（MCPServer），原生支持 `uvx` 随选即用，完美兼容 VS Code Cline、Claude Desktop 等开发环境。同时支持超短指令别名 `tg-agent`。

[![PyPI Version](https://img.shields.io/pypi/v/mcp-telegram-agent?color=blue&logo=pypi)](https://pypi.org/project/mcp-telegram-agent/)
[![Python Versions](https://img.shields.io/pypi/pyversions/mcp-telegram-agent?logo=python)](https://pypi.org/project/mcp-telegram-agent/)
[![PyPI Downloads](https://static.pepy.tech/personalized-badge/mcp-telegram-agent?period=total&units=INTERNATIONAL_SYSTEM&left_color=GREY&right_color=BLUE&left_text=downloads)](https://pepy.tech/projects/mcp-telegram-agent)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

[English](README.md) · [繁體中文](README.zh-TW.md) · **简体中文**

</div>

> 🔐 **别再把你的个人 Telegram 账号凭证交给 AI。**
>
> **mcp-telegram-agent** 是轻量、零登录风险的通知与文件递送工具——只需一组 Bot Token，就能把本机文件、报表、互动键盘与丰富通知直接送到你的手机。

---

## ✨ 项目亮点

* **纯机器人架构** — 仅需 Bot Token 与 Chat ID，无需输入手机验证码登录个人账号，零账号封禁风险。
* **双命令行入口** — 同时支持标准 `mcp-telegram-agent` 与精简 `tg-agent` 别名命令。
* **完整键盘支持** — 原生支持内联按钮（超链接与回调数据）以及手机底部回复键盘。
* **本机文件与相册** — 轻松发送日志、报表、源代码、图片、语音、视频，以及 2 至 10 个项目的多媒体相册。
* **丰富互动组件** — 支持即时投票、测验、地图经纬度坐标、电话名片及官方动画表情符号。
* **状态与消息生命周期维护** — 支持实时广播机器人输入状态，并能动态更新或删除指定消息。
* **互动接收** — 以 `get_updates` / `wait_for_reply` 拉取或长轮询用户回复（文字消息、内联按钮点击、投票作答），并用 `answer_callback_query` 回应按钮点击。
* **uvx 极速启动** — 免去手动创建虚拟环境与安装依赖的繁琐步骤。

---

## 🚀 快速开始

### 1️⃣ 申请 Telegram 机器人并获取 Token

1. 打开 Telegram 搜索 **@BotFather**（有蓝色勾勾认证）。
2. 发送 `/newbot`，按提示输入显示名称，再取一个以 `bot` 结尾的账号名（如 `my_alert_bot`）。
3. BotFather 会回复你的 **Bot Token**，格式如 `123456789:AAHxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`。请妥善保管——拿到此 Token 的人就能完全控制你的机器人。
4. **重要**：打开新机器人的聊天窗口按下 **Start**（或发送 `/start`）。用户若从未与机器人开启过对话，机器人是无法主动发消息给他的。

### 2️⃣ 获取个人 Chat ID

1. 发送任意消息（如「hi」）给你的新机器人。
2. 用浏览器打开下列网址，将 `<YOUR_BOT_TOKEN>` 换成你的 Token：
   `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
3. 在返回的 JSON 中找到 `"chat":{"id": 123456789, ...}`，该数值即是你的 **Chat ID**。
   * 替代做法：发送任意消息给 `@userinfobot`，它会直接回复你的 ID。

### 3️⃣ 发送到群组或频道（可选）

* 先**把机器人加入群组**（群组设置 → 加入成员）。频道则须将机器人设为**管理员**才能发文。
* **群组 ID 为负数**（如 `-1001234567890`）。获取方式：
  * 临时把 `@userinfobot` 拉进群组，转发一条群组消息给它即可查得；**或**
  * 先在 @BotFather 执行 `/setprivacy` → 选择你的机器人 → **Disable**（关闭隐私模式），在群组内发一条消息后，再以 `getUpdates` 查询。
* 机器人一旦成为群组／频道成员，即可直接发送消息，无需额外配置。

### 4️⃣ 运行时发送到任意 Chat

`TELEGRAM_DEFAULT_CHAT_ID` 只是**默认收件人**。所有工具都接受可选的 `chat_id` 参数，你可以直接对 AI 代理说「把这条消息发到 chat ID -1001234567890」：

* **未提供** `chat_id` → 消息送到配置文件中的 `TELEGRAM_DEFAULT_CHAT_ID`。
* **有提供** `chat_id` → 消息改送到指定的用户／群组／频道。
* 前提：机器人必须已在该群组／频道内（或该用户已对机器人按过 Start）。

### 5️⃣ 客户端配置示例

在 MCP 配置文件（例如 VS Code 的 `cline_mcp_settings.json` 或 `claude_desktop_config.json`）中加入以下内容。

#### ✅ 推荐配置（启用全部功能）

一个区块同时启用**发送**与**互动接收**——填入你的令牌、chat_id 与白名单即可：

```json
{
  "mcpServers": {
    "Telegram": {
      "command": "uvx",
      "args": ["mcp-telegram-agent"],
      "env": {
        "TELEGRAM_BOT_TOKEN": "你的_BOT_TOKEN",
        "TELEGRAM_DEFAULT_CHAT_ID": "你的_CHAT_ID",
        "TELEGRAM_ALLOWED_CHAT_IDS": "123456789,-1001234567890",
        "TELEGRAM_ALLOWED_USER_IDS": "123456789"
      }
    }
  }
}
```

> 💡 **四个环境变量皆为可选。** 缺少任一变量时服务器仍会正常启动，只在实际调用相关工具时，返回清晰的错误说明。各变量作用：

* `TELEGRAM_BOT_TOKEN` — 你的 Bot Token，所有发送类工具的必要凭证。
* `TELEGRAM_DEFAULT_CHAT_ID` — 默认收件人；工具调用未提供 `chat_id` 时的目标。
* `TELEGRAM_ALLOWED_CHAT_IDS`／`TELEGRAM_ALLOWED_USER_IDS` — 互动接收白名单，让 AI 代理能「读回」你的回复（文字消息、内联按钮点击、投票作答），行为细节见第 6️⃣ 步。省略时互动接收关闭，`get_updates` / `wait_for_reply` 会返回设置提示。
* `TELEGRAM_STATE_DIR`（未列入示例的进阶选项）— `getUpdates` offset 持久化文件的存放目录，未设置时默认写入系统临时目录下的 `mcp-telegram-agent` 子目录。

> 💡 想先进行不带凭证的试运行，可整段省略 `env` 区块，之后依工具返回的错误提示逐项补齐即可。

### 6️⃣ 互动接收（白名单）行为

推荐配置已同时填入两份白名单，`get_updates` / `wait_for_reply` 因此可拉取或长轮询你的回复。行为细节：

* `TELEGRAM_ALLOWED_CHAT_IDS` — Chat ID 白名单（逗号分隔）；已设置时，来自其他聊天室的更新一律过滤（群组 ID 为负数）。`poll_answer` 事件没有 `chat_id`，无法与此名单比对。
* `TELEGRAM_ALLOWED_USER_IDS` — User ID 白名单（逗号分隔）；已设置时，更新也会以 User ID 过滤。更新只要命中**任一**已设置的名单即放行（未设置的名单不参与判定）。
* 首次调用注意：第一次调用 `get_updates`（尚无状态文件）时，Telegram 会返回全部未确认的 pending updates，且 `mark_read` 默认 true 会将其读取推进；若不想消耗历史积压，第一次调用请先用 `mark_read: false` 预览。
* limit 只限制单次返回笔数：offset 仅推进到实际返回的最后一笔，被截断的其余符合项目会留待下次调用。未符合白名单或 types 条件的更新仍会被读取推进（offset 为单一数据流，无法单独保留某个类型或某间聊天室的更新）。
* 未设置白名单时，`get_updates` / `wait_for_reply` 只会返回设置提示。修改 `env` 后请重启 MCP 服务器。

> ⚠️ **时机是关键：** Telegram 的 callback_query 只有数秒有效。`get_updates` 与 `wait_for_reply` 预设开启 `auto_answer`，取回按钮点击的当下就会自动应答；仅当关闭该选项时，才需要在收到按钮点击后立刻调用 `answer_callback_query`——间隔过长会收到 `query is too old`（平台限制，并非程序错误）。

---

## 🧰 工具列表

| 工具 | 说明 |
| --- | --- |
| `send_text_message` | 发送 Markdown 与 HTML 格式化文字，支持内联按钮或底部键盘。 |
| `send_local_document` | 传送各类本机报告、CSV、ZIP 或源代码文件。 |
| `send_local_photo` | 发送图片文件并支持即时全屏预览。 |
| `send_local_video` | 发送本机视频并支持内嵌播放器。 |
| `send_local_audio_or_voice` | 发送音频或语音留言。 |
| `send_media_album` | 批量发送 2 至 10 张图片或视频组成相册轮播。 |
| `send_poll` | 创建互动式单选、多选投票或附带解析的标准测验。 |
| `send_location` | 传送经纬度地理位置坐标地图。 |
| `send_contact` | 传送名片联系人信息。 |
| `send_dice` | 发送随机动画表情，如骰子与老虎机等。 |
| `send_chat_action` | 向客户端显示当前操作状态，如输入中与上传文件中。 |
| `edit_message_text` | 动态更新既有消息内容与按钮。 |
| `delete_message` | 清理特定暂存或历史消息。 |
| `get_updates` | 一次性拉取待处理更新（消息、按钮点击、投票作答），不等待新消息。 |
| `wait_for_reply` | 长轮询等待用户下一条回复，超时自动返回。 |
| `answer_callback_query` | 回应内联按钮点击以关闭加载动画，可附提示文字或打开网址。 |

---

## 💬 使用示例

完成配置后，直接用自然语言对 AI 代理下指令，代理会自动挑选合适的工具。以下列出常见指令与代理实际调用的工具参数：

### 📢 发送格式化通知

> 「在 Telegram 通知我今晚的构建成功了，并附上一个连到 https://example.com 的按钮」

```json
{
  "tool": "send_text_message",
  "arguments": {
    "text": "✅ *今晚构建成功！*",
    "parse_mode": "Markdown",
    "inline_buttons": [[{"text": "仪表板", "url": "https://example.com"}]]
  }
}
```

### 📁 传送本机文件

> 「把 `logs/app.log` 传到我的 Telegram，并摘要错误内容」

```json
{
  "tool": "send_local_document",
  "arguments": {
    "file_path": "logs/app.log",
    "caption": "错误日志摘要：3 次超时警告"
  }
}
```

### 🖼️ 发送相册

> 「把 `screenshots/` 里的三张截图以一则相册传到我的 Telegram」

```json
{
  "tool": "send_media_album",
  "arguments": {
    "file_paths": ["screenshots/1.png", "screenshots/2.png", "screenshots/3.png"],
    "caption": "最新 UI 截图"
  }
}
```

### 🗳️ 在群组发起测验

> 「在 chat ID -1001234567890 发一则测验：HTTPS 使用哪个端口？选项 80／443／8080，正解 443，并附简短解析」

```json
{
  "tool": "send_poll",
  "arguments": {
    "chat_id": "-1001234567890",
    "question": "HTTPS 使用哪个端口？",
    "options": ["80", "443", "8080"],
    "type": "quiz",
    "correct_option_id": 1,
    "explanation": "HTTPS 默认使用端口 443。"
  }
}
```

### ♻️ 更新或清理消息

> 「把那条部署通知改成『已完成』，然后删除旧的提醒（ID 120）」

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

### 📨 等待回复并确认按钮点击

> 「传给我一个是/否问题的内联按钮，等我点击后回报我选了什么」

```json
{
  "tool": "send_text_message",
  "arguments": {
    "text": "现在部署到正式环境？",
    "inline_buttons": [[{"text": "好", "callback_data": "deploy:yes"}, {"text": "不要", "callback_data": "deploy:no"}]]
  }
}
```

```json
{
  "tool": "wait_for_reply",
  "arguments": { "types": ["callback_query"], "timeout": 25 }
}
```

```json
{
  "tool": "answer_callback_query",
  "arguments": { "callback_query_id": "<点击事件中的 callback_query.id>", "text": "🚀 部署中…" }
}
```

> 💡 需先于第 5️⃣ 步设置白名单。`get_updates` 适合一次性非阻塞查看（可加 `mark_read: false` 先查看不消耗更新）；`wait_for_reply` 则是长轮询直到收到回复。按钮点击会在取回当下自动应答；仅当需要自定义提示、弹窗或网址时才传 `auto_answer: false` 并改用 `answer_callback_query`。

> 💡 未提供 `chat_id` 时，消息送到 `TELEGRAM_DEFAULT_CHAT_ID`；明确传入 `chat_id` 即可发送给任何用户、群组或频道——见上方第 4️⃣ 步。

---

## 🛠️ 开发与发布流程

* 功能开发一律先进 **`main`** 分支（PR 合并至 main）。
* 发布**仅**通过 **`release`** 分支：自 `main` 建立 PR 指向 `release`，在 PR 中调升 `pyproject.toml` 的 `version` 后合并，CI 即自动构建并发布至 PyPI，同时自动创建对应的 GitHub Release（`v*` 标签与自动生成的 release notes）。
* 若未调升版本，workflow 会明确警告并跳过发布——纯文档 PR 不会让 CI 失败。
* `release` 分支已启用分支保护，禁止直接 push，一律经 PR 发布。

---

## 📄 授权条款

本项目采用 MIT 授权协议开源发布。
