![](pic/logo.png)

**An asynchronous Telegram channel monitoring and AI-powered content rewriting bot built with Python**

TeleMorphPyBOT monitors configured public Telegram channels, detects newly published posts, removes configurable promotional signatures, rewrites the content with Google Gemini, and publishes the resulting text to a designated Telegram channel.

The project also includes an interactive Telegram administration panel for managing channels, prompts, filtering rules, runtime settings, publication history, and bot execution.

---

## Table of Contents

- [Overview](#overview)
- [Key Features](#key-features)
- [How It Works](#how-it-works)
- [Requirements](#requirements)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Environment Configuration](#environment-configuration)
- [Application Configuration](#application-configuration)
- [Telegram Channel Setup](#telegram-channel-setup)
- [Running the Bot](#running-the-bot)
- [Administration Panel](#administration-panel)
- [Project Structure](#project-structure)
- [Logging and Publication History](#logging-and-publication-history)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)

---

## Overview

TeleMorphPyBOT is designed to automate the collection and republishing of text content from Telegram channels.

It periodically checks a configurable list of source channels. When a new post is detected, the bot:

1. Retrieves the post text from the source channel's public Telegram web preview.
2. Removes trailing promotional or signature content using configurable stop words.
3. Sends the remaining text to the Google Gemini API for rewriting.
4. Appends a link to the original post.
5. Publishes the rewritten content to the configured target channel.
6. Records publication metadata in the local history.

The bot runs asynchronously and provides an interactive administration interface directly in Telegram.

> **Scope:** The current parser retrieves text from publicly accessible Telegram channel previews. It is not a general-purpose private-channel or media downloader.

## Key Features

### Automated Channel Monitoring
- Monitor multiple configurable public Telegram channels.
- Periodically check channels for newly published posts.
- Process detected posts in chronological order.
- Maintain per-channel processing state during operation.

### AI-Powered Content Rewriting
- Integrate with the Google Gemini API.
- Use a customizable prompt template.
- Configure the Gemini model, output token limit, and generation temperature.
- Track token usage returned by the Gemini API.

### Content Filtering
- Remove trailing promotional signatures and unwanted lines.
- Manage stop words through a JSON configuration file.
- Skip posts that become empty after filtering.

### Telegram Publishing
- Publish rewritten text to a configurable target channel.
- Append a direct link to the original Telegram post.
- Use the Telegram Bot API for message delivery.

### Interactive Administration
- Manage source channels and the target channel.
- View and edit the AI prompt.
- Add or remove stop words.
- Update supported runtime and Gemini settings.
- View bot status and recent publication history.
- Pause or resume the parsing cycle.
- Stop the bot through the administration interface.

### Operational Visibility
- File-based application logging.
- Publication history with timestamps and source references.
- Token usage and processing-time records.
- Configurable log verbosity.

---

## How It Works

The application consists of several cooperating components:

| Component | Responsibility |
|---|---|
| `main.py` | Application lifecycle, asynchronous monitoring loop, and orchestration |
| `tg_parser.py` | Retrieves posts from public Telegram channel previews |
| `gemini.py` | Sends text to Google Gemini and handles generated responses |
| `publisher.py` | Publishes messages through the Telegram Bot API |
| `filters.py` | Removes configured trailing signatures and promotional content |
| `config_manager.py` | Loads, initializes, and saves application configuration |
| `admin_ui.py` | Implements the interactive Telegram administration panel |
| `history_manager.py` | Stores and retrieves publication history |

### Processing Workflow

```text
Configured Source Channels
          |
          v
  Telegram Web Parser
          |
          v
   New Post Detection
          |
          v
   Signature Filtering
          |
          v
     Google Gemini
   (Content Rewriting)
          |
          v
 Append Original Post URL
          |
          v
   Telegram Publisher
          |
          v
     Target Channel
          |
          v
  Publication History
```

**First-run behavior:** On the first scan of a source channel, the application stores the latest available post ID as its baseline. It does not import or publish the channel's existing backlog. Subsequent scans process posts detected after that baseline.

---

## Requirements

- Python **3.10+ or later**.
- A Telegram bot token.
- A Google Gemini API key.
- Access to the public Telegram channels that you want to monitor.
- A Telegram target channel where the bot can publish messages.
- An internet connection.

The Python dependencies are pinned in [`requirements.txt`](requirements.txt).

## Prerequisites

Before installing the application, prepare the following:

1. **Telegram bot:** Create a bot through [@BotFather](https://t.me/BotFather) and obtain its API token.
2. **Google Gemini API:** Obtain an API key through [Google AI Studio](https://aistudio.google.com/app/apikey).
3. **Source channels:** Identify the public Telegram channels to monitor.
4. **Target channel:** Create or select the channel where rewritten posts will be published.
5. **Administrator access:** Make sure the bot can publish messages in the target channel. See [Telegram Channel Setup](#telegram-channel-setup).

---

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/tr4itor/TeleMorphPyBOT.git
cd TeleMorphPyBOT
```

### 2. Create a virtual environment

**Linux / macOS**

```bash
python3 -m venv .autobot
source .autobot/bin/activate
```

**Windows (PowerShell)**

```powershell
python -m venv .autobot
.autobot\Scripts\Activate.ps1
```

### 3. Install dependencies

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Configure environment variables

Create a `.env` file in the project root directory. See [Environment Configuration](#environment-configuration).

### 5. Initialize application configuration

The application automatically creates the `config/` directory and its default configuration files when `ConfigManager` is initialized.

You can start the bot once to generate the files, then stop it and review the configuration before normal operation. Alternatively, create the directory and files manually using the examples in [Application Configuration](#application-configuration).

But if for some reason the files were not created or were lost, the `config` folder contains templates.

---

## Environment Configuration

The `.env` file must be located in the project root.

```dotenv
TELEGRAM_TOKEN=your_telegram_bot_token
```

| Variable | Required | Description |
|---|---:|---|
| `TELEGRAM_TOKEN` | Yes | Telegram Bot API token used by the bot |

---

## Application Configuration

All application configuration is stored in the `config/` directory.

The configuration manager creates the following files automatically if they do not exist:

```text
config/
├── admins.json  # accounts with access to the bot
├── channels.json # channels that will be monitored
├── prompt.txt # prompt for Gemini
├── settings.json # general settings
├── stopwords.json 
└── target_channel.json # the channel to which final messages will be sent
```

### `admins.json`

Contains Telegram user IDs that are allowed to access the administration panel.

```json
{
  "admins": [
    123456789
  ]
}
```

Replace the example ID with the numeric Telegram user ID of each authorized administrator.

Only users listed in this file can use the bot's administration interface.

### `channels.json`

Defines the source channels monitored by the bot.

```json
{
  "channels": [
    "source_channel_one",
    "source_channel_two"
  ]
}
```

Use public channel usernames without the `@` prefix.

### `target_channel.json`

Defines the destination channel for published messages.

```json
{
  "target": "your_target_channel_id(-100...)"
}
```


The bot must have administrator privileges in this target channel and permission to post messages. See [Telegram Channel Setup](#telegram-channel-setup).

### `prompt.txt`

Contains the prompt template sent to Google Gemini.

The application inserts the source post text using Python's string formatting. **The prompt must contain a `{}` placeholder** at the position where the source text should be inserted.

**Example:**

```text
Rewrite the following text. Preserve all factual information while substantially changing the wording, sentence structure, and style. Return only the final publication-ready text, without explanations or additional commentary.

Text: {}

```

The `{}` placeholder is required by the current implementation. Without it, the source post text will not be inserted into the prompt as intended.

### `stopwords.json`

Contains words and phrases used to identify trailing promotional signatures.

```json
{
  "stopwords": [
    "subscribe",
    "t.me",
    "donate",
    "join our channel"
  ]
}
```

The filtering logic checks trailing lines and removes them when they contain configured stop words. It does not perform general-purpose semantic moderation or remove matching phrases from arbitrary positions in the post.

### `settings.json`

Controls parsing behavior, logging, and Gemini generation parameters.

```json
{
  "parse_interval": 60,
  "log_level": "INFO",
  "gemini_model": "gemini-3.1-flash-lite",
  "max_tokens": 4000,
  "temperature": 0.7,
  "gemini_api_key": ""
}
```

| Setting | Description |
|---|---|
| `parse_interval` | Delay, in seconds, between parsing cycles |
| `log_level` | Logging verbosity, such as `INFO`, `DEBUG`, or `WARNING` |
| `gemini_model` | Gemini model identifier used for content generation |
| `max_tokens` | Maximum output token count requested from Gemini |
| `temperature` | Gemini generation temperature |
| `gemini_api_key` | Gemini API key|

The Gemini model identifier and generation limits must be supported by the Google Gemini API and the account associated with the API key.

---

## Telegram Channel Setup

Publishing permissions are essential for the bot to work correctly.

### Grant Administrator Rights in the Target Channel

**The bot must be added as an administrator of the target Telegram channel.** It must also have the permission to publish messages.

Without the required administrator and posting permissions, Telegram will reject publication requests.

### Configure Administrator Access to the Bot

The bot's own administration panel has a separate access-control list.

Add the numeric Telegram user IDs of trusted operators to `config/admins.json`. Being an administrator of the target channel does not automatically grant access to the bot's administration panel, and being listed in `admins.json` does not automatically grant channel-publishing permissions.

---

## Running the Bot

From the project root, with the virtual environment activated and configuration in place:

```bash
python3 main.py
```

The application will:

1. Initialize the Telegram bot.
2. Initialize the parser and Gemini client.
3. Register the administration handlers.
4. Start Telegram update polling.
5. Start the asynchronous channel-monitoring cycle.

Keep the process running for continuous monitoring. Stop the process using your process manager or terminal when needed.

---

## Administration Panel

Open a private Telegram conversation with the bot and send:

```text
/start
```

The `/start` command opens the interactive administration panel for users whose Telegram IDs are present in `config/admins.json`.

The panel provides the following areas:

| Panel section | Available operations |
|---|---|
| Channels | View, add, and remove source channels |
| Target Channel | View and update the destination channel |
| Prompt | View and edit the Gemini prompt |
| Stop Words | View, add, and remove filtering terms |
| Settings | Edit supported parsing and Gemini settings |
| Status | Inspect the current bot and parsing-cycle status; pause or resume processing |
| History | Review recent publication records and clear the history |
| Stop Bot | Request bot shutdown |

The administration interface uses inline Telegram buttons and interactive text input. Some changes take effect when the relevant configuration is read again or when the next parsing cycle begins.

---

## Project Structure

```text
TeleMorphPyBOT/
├── admin_ui.py             # Interactive Telegram administration panel
├── config_manager.py       # Configuration initialization and management
├── filters.py              # Promotional signature filtering
├── gemini.py               # Google Gemini API integration
├── history.json            # Local publication history
├── history_manager.py      # Publication history management
├── main.py                 # Application entry point and orchestration
├── publisher.py            # Telegram message publishing
├── requirements.txt        # Pinned Python dependencies
├── tg_parser.py             # Public Telegram channel parser
├── .env                    # Local secrets 
├── config/                 # Generated application configuration
│   ├── admins.json
│   ├── channels.json
│   ├── prompt.txt
│   ├── settings.json
│   ├── stopwords.json
│   └── target_channel.json
├── logs/                   # Runtime log files (created automatically)
└── state.json              # Runtime source-channel processing state
```

Some files and directories are generated at runtime and may not be present in a fresh repository checkout.

---

## Logging and Publication History

### Logs

The application creates a `logs/` directory and writes timestamped log files when it starts.

The log level is controlled by `log_level` in `config/settings.json`.

### Publication History

`history.json` stores recent publication records, including:

- Publication timestamp.
- Source channel.
- Original post identifier and URL.
- Published text (truncated to a maximum of 500 characters per record).
- Gemini token usage.
- Processing time.

The history manager retains up to 100 records by default.

---

## Troubleshooting

| Problem | Possible cause | Suggested action |
|---|---|---|
| `TELEGRAM_TOKEN not set in .env` | Missing or incorrectly named environment variable | Check that `.env` exists in the project root and contains `TELEGRAM_TOKEN` |
| `GEMINI_API_KEY not set in settings.json` | Gemini key is not configured | Set `GEMINI_API_KEY` in `gemini_api_key` in `settings.json` |
| Telegram rejects a publication request | The bot is not an administrator or lacks posting permission | Grant administrator rights and enable **Post Messages** in the target channel |
| No source posts are detected | Invalid channel username, inaccessible channel, or no new posts | Verify the public channel username and check the application logs |
| Gemini returns an API error | Invalid key, unsupported model, quota limit, or API access issue | Verify the key, model identifier, and Google AI Studio/API quota |
| Administration panel does not respond to a user | The user's Telegram ID is not in the administrator list | Add the numeric user ID to `config/admins.json` |
| Rewritten text does not include the source content | The prompt template is missing its `{}` placeholder | Add the placeholder to `config/prompt.txt` |

For further diagnosis, inspect the latest file in `logs/`.

---

## Contributing

**Contributions, bug reports, and suggestions are welcome.**

When submitting a pull request:

1. Keep changes focused and clearly documented.
2. Preserve the existing asynchronous application design.
3. Avoid committing credentials, local configuration, logs, or runtime data.
4. Include reproduction steps for bug fixes where applicable.

For significant changes, consider opening an issue first to discuss the proposed implementation.


