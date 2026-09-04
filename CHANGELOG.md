# Changelog

## Unreleased

- Restored the two-window Codex quota layout (5-hour + weekly) in a single window.
- `primary_window` is shown as the 5-hour quota and `secondary_window` as the weekly quota.
- Falls back to the largest available window when the weekly window is missing, without duplicating the same window twice.
- Added a full-height pace tick on each quota bar (green = ahead, white = on pace, yellow/red = over pace).
- The 5-hour row hides the daily-pace label (not meaningful for a 5-hour window).
- `launch.vbs` prefers a local Python 3.12 install and falls back to `PATH`.
- Regenerated the screenshot for the dual-window layout.
- Updated English and Traditional Chinese READMEs for the dual-window format.

## Previously (weekly-only)

- Added an expected-remaining marker based on an even 14.3% daily pace.
- Added `Ahead`, `On pace`, and `Over pace` status to the weekly quota row.
- Updated the parser and UI for the weekly-only Codex quota format.
- Added support for a single 7-day `primary_window` and an explicit `weekly_window`.
- Invalidated legacy two-window cache data and replaced the 5-hour/7-day rows with one weekly quota bar.
- Switched the primary usage endpoint to `https://chatgpt.com/backend-api/wham/usage`.
- Kept `https://chatgpt.com/backend-api/codex/usage` as a fallback endpoint.
- Changed the usage request User-Agent to `codex-cli` to avoid `403` responses seen with newer request fingerprints.
- Added clearer error states for auth, network, timeout, HTTP, and blocked responses.
- Added local last-good cache support so the widget can keep showing the previous successful quota reading after a failed refresh.
- Added local diagnostic logging to `codex_quota_overlay.log`.
- Enlarged the widget window and adjusted spacing so the footer is not clipped.
- Rewrote English and Traditional Chinese README files without private local information.
