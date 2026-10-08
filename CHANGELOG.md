# Changelog

## Unreleased

### Fixes

- Background fetch threads no longer call into Tk; results go through a queue
  drained by the main thread, because Tcl/Tk is not thread-safe.
- The auto-refresh chain is scheduled from the main thread and survives a failed
  thread start or a fetch that produced no result.
- Cached rows keep the raw `reset_at`, so the countdown and pace are recomputed
  on render instead of showing the values frozen when the cache was written.
  Legacy cache files without `reset_at` still fall back to the stored strings.
- `socket.timeout` is classified as `timeout` on Python 3.9, where it is not an
  alias of `TimeoutError`.
- Consecutive failures back off: 30s, 60s, 120s, 240s, capped at 300s, and the
  footer shows the current wait. A successful read resets it to 30s.
- The log is trimmed to its last 1000 lines once it passes 200 KB.
- `auth.json` is re-read before writing. If the Codex CLI refreshed the file
  while the overlay was on the network, the file wins and the write is skipped
  instead of clobbering a fresher refresh token. The refreshed token is also
  kept in memory, so an expired token is not re-fetched on every cycle.
- Only one instance runs at a time: a second launch exits with a short message
  instead of opening a duplicate widget. The lock is an OS-level lock on
  `.overlay.lock`, not a PID check, so a crashed instance never leaves a stale
  lock behind.

### Layout

- Restored the two-window Codex quota layout (5-hour + weekly) in a single window.
- `primary_window` is shown as the 5-hour quota and `secondary_window` as the weekly quota.
- Falls back to the largest available window when the weekly window is missing, without duplicating the same window twice.
- Added a full-height pace tick on each quota bar (green = ahead, white = on pace, yellow/red = over pace).
- The 5-hour row hides the daily-pace label (not meaningful for a 5-hour window).
- `launch.vbs` prefers a local Python 3.12 install and falls back to `PATH`.
- Regenerated the screenshot for the dual-window layout.
- Updated English and Traditional Chinese READMEs for the dual-window format.

### Known minor issues

- `quota_mode` is always written as `dual` while the cache loader still accepts
  the legacy `weekly` value.
- The window is taller than its content, leaving a gap above the footer.
- No `LICENSE` file is present even though both READMEs say MIT.
- `docs/superpowers/` still describes the macOS dashboards and the older
  single-row layout.

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
