[English](README.md) | [繁體中文](README_zh.md)

# Codex Quota Overlay

Real-time desktop widget showing your OpenAI Codex / ChatGPT quota usage.  
Pulls data directly from the official `chatgpt.com/backend-api/codex/usage` endpoint.

![screenshot](screenshot.png)

## Features

- **Live quota bars** — 5-hour and 7-day rolling windows  
- **Color-coded** — green (≥50%), yellow (20–49%), red (<20%)  
- **Auto-refresh** every 30 seconds  
- **Always-on-top toggle** via right-click menu  
- **Zero dependencies** — stdlib only (tkinter, json, urllib, threading)  
- **Windows native** — tiny window, no browser, no Electron  

## Requirements

- **Windows 10/11**
- **Python 3.9+** with tkinter (included in the standard Windows Python installer)
- **Codex Desktop** installed and logged in via ChatGPT

The tool reads your access token from `%USERPROFILE%\.codex\auth.json` — the same file Codex Desktop uses internally. No credentials are ever stored or transmitted elsewhere.

## Quick Start

1. Make sure [Codex Desktop](https://codex.openai.com/) is installed and you're logged in.
2. Double-click `launch.vbs`.

A small dark window appears in the top-left corner. Right-click for options.

## Manual Run

```bash
python codex_quota_overlay.py
```

Or without the console window:

```bash
pythonw codex_quota_overlay.py
```

## How It Works

```
auth.json (local)  →  access_token
                            ↓
chatgpt.com/backend-api/codex/usage  →  rate_limit JSON
                            ↓
                    tkinter overlay (auto-refresh 30s)
```

The endpoint returns:

```json
{
  "plan_type": "plus",
  "rate_limit": {
    "allowed": true,
    "limit_reached": false,
    "primary_window": {
      "used_percent": 35,
      "limit_window_seconds": 18000,
      "reset_at": 1781022613
    },
    "secondary_window": {
      "used_percent": 28,
      "limit_window_seconds": 604800,
      "reset_at": 1781188385
    }
  }
}
```

## Privacy

- Your access token is read from `auth.json` on disk and used **only** for the single API call to `chatgpt.com/backend-api/codex/usage`.
- No data is logged, stored, or sent anywhere else.
- The source is ~250 lines — you can audit it in 5 minutes.

## License

MIT
