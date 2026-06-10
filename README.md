# Codex Quota Overlay for Windows

[English](README.md) | [Traditional Chinese](README_zh.md)

A small Windows desktop widget for checking OpenAI Codex / ChatGPT quota usage.

The overlay reads your local Codex OAuth token from `%USERPROFILE%\.codex\auth.json`, calls the ChatGPT usage endpoint, and shows the 5-hour and 7-day rolling quota windows in a compact Tkinter window.

![screenshot](screenshot.png)

## What Changed

- Uses `https://chatgpt.com/backend-api/wham/usage` first.
- Falls back to `https://chatgpt.com/backend-api/codex/usage`.
- Uses a legacy `codex-cli` User-Agent because the newer Codex usage endpoint can return `403` for some request fingerprints.
- Shows clearer status labels such as `blocked 403`, `timeout`, `login missing`, and `network error`.
- Keeps the last successful quota reading visible if a later refresh fails.
- Writes local diagnostic messages to `codex_quota_overlay.log`.
- Stores the last successful reading in `codex_quota_overlay_cache.json`.
- Refreshed the widget layout with a larger card and cleaner spacing.

## Features

- Live 5-hour and 7-day quota bars.
- Color-coded remaining quota: green, yellow, red.
- Auto-refresh every 30 seconds.
- Right-click menu for refresh, always-on-top, opening the log folder, and closing the widget.
- No third-party Python dependencies.
- Windows native: tiny Tkinter app, no browser, no Electron.

## Requirements

- Windows 10 or Windows 11.
- Python 3.9+ with Tkinter.
- Codex Desktop or Codex CLI logged in with ChatGPT auth.

## Quick Start

1. Make sure Codex is installed and logged in.
2. Double-click `launch.vbs`.
3. Right-click the widget for options.

## Manual Run

```powershell
python codex_quota_overlay.py
```

Or without a console window:

```powershell
pythonw codex_quota_overlay.py
```

## How It Works

```text
%USERPROFILE%\.codex\auth.json
        -> access token
        -> chatgpt.com/backend-api/wham/usage
        -> rate_limit JSON
        -> Tkinter overlay
```

Example response shape:

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

- The access token is read from the local Codex auth file and sent only to `chatgpt.com` for the usage request.
- The repository does not include tokens, account email, personal paths, or quota snapshots.
- Runtime files such as logs and cache are ignored by Git.

## License

MIT
