# Codex Quota Overlay for Windows

[English](README.md) | [Traditional Chinese](README_zh.md)

A small Windows desktop widget for checking OpenAI Codex / ChatGPT quota usage.

The overlay reads your local Codex OAuth token from `%USERPROFILE%\.codex\auth.json`, calls the ChatGPT usage endpoint, and shows the current 5-hour and weekly quotas in a compact Tkinter window.

## What Changed

- Updated for the restored two-window Codex quota format (5-hour + weekly).
- Shows both quota windows in one window: 5-hour on top, weekly below.
- Treats `primary_window` as the 5-hour quota and `secondary_window` as the weekly quota.
- Falls back to the largest available window when the weekly window is missing, without duplicating the same window twice.
- Added a full-height pace tick on each quota bar: where usage *should* be right now.
  - Green tick = ahead of pace (using less than expected).
  - White tick = on pace.
  - Yellow/red tick = over pace (using more than expected).
- The 5-hour row hides the daily-pace label because a daily pace is not meaningful for a 5-hour window.
- Uses `https://chatgpt.com/backend-api/wham/usage` first.
- Falls back to `https://chatgpt.com/backend-api/codex/usage`.
- Uses a legacy `codex-cli` User-Agent because the newer Codex usage endpoint can return `403` for some request fingerprints.
- Shows clearer status labels such as `blocked 403`, `timeout`, `login missing`, and `network error`.
- Keeps the last successful quota reading visible if a later refresh fails.
- Writes local diagnostic messages to `codex_quota_overlay.log`.
- Stores the last successful reading in `codex_quota_overlay_cache.json`.
- `launch.vbs` prefers a local Python 3.12 install (`%LocalAppData%\Programs\Python\Python312`) and falls back to `PATH`.

## Features

- Live 5-hour and weekly quota bars in one compact window.
- Full-height pace tick showing where usage should be right now.
- `Ahead`, `On pace`, or `Over pace` guidance at a glance.
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
      "used_percent": 0,
      "limit_window_seconds": 18000,
      "reset_at": 1781188385
    },
    "secondary_window": {
      "used_percent": 34,
      "limit_window_seconds": 604800,
      "reset_at": 1781188385
    }
  }
}
```

`primary_window` is the 5-hour quota and `secondary_window` is the weekly
quota. The full-height tick on each bar shows how much quota would remain if
usage were spread evenly across that window. This is a pace guide, not a
separate limit; unused quota remains available until the window resets.

## Privacy

- The access token is read from the local Codex auth file and sent only to `chatgpt.com` for the usage request.
- The repository does not include tokens, account email, personal paths, or quota snapshots.
- Runtime files such as logs and cache are ignored by Git.

## License

MIT
