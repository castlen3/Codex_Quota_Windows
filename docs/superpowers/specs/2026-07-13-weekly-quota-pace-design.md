# Weekly Quota Pace Design

> **Historical.** Written while the quota was weekly-only. The pace formula is
> still current, but the Windows overlay now renders the 5-hour and weekly rows
> again, so "materially shorter than the old two-row version" no longer describes
> this repository, and the 8765/8766 and `/lite` views are not part of it.

## Goal

Make a weekly-only Codex quota immediately understandable. The user should be
able to tell whether current usage is ahead of or behind an even seven-day pace
without mentally converting remaining quota into days.

The design applies consistently to:

- the local 8765 Codex dashboard;
- the local 8766 Codex + LM Studio dashboard and `/lite` page;
- the Windows Tkinter overlay.

## Chosen Visual Model

Use one horizontal remaining-quota bar with a vertical pace marker.

- The filled portion shows the actual percentage remaining.
- A thin luminous vertical marker shows the percentage that should remain at
  the current point in the seven-day window if usage is evenly distributed.
- Supporting text shows `Ahead N%` when actual remaining quota is above the
  marker and `Over pace N%` when it is below the marker.
- `Daily pace 14.3%` explains the guide without implying a separate daily
  allowance.
- The existing reset countdown remains visible.

This is preferred over a seven-segment day chart because it adds less height,
and over a circular gauge because the marker is easier to compare on a linear
scale.

## Pace Calculation

Use the API window duration when available and fall back to seven days.

```text
window_seconds = windowMinutes * 60, otherwise 604800
remaining_seconds = clamp(reset_at - now, 0, window_seconds)
expected_remaining = remaining_seconds / window_seconds * 100
actual_remaining = clamp(100 - usedPercent, 0, 100)
pace_delta = actual_remaining - expected_remaining
```

Examples:

- At the start of the window, expected remaining is 100%.
- After 3.5 days, expected remaining is 50%.
- With 72% actual remaining after 3.5 days, display `Ahead 22%`.
- With 38% actual remaining after 3.5 days, display `Over pace 12%`.

Display deltas rounded to the nearest whole percentage point. A delta whose
absolute value is below 1 percentage point displays `On pace`.

## Tone And Status

- `Ahead` and `On pace`: use the existing green/teal online accent.
- `Over pace` by up to 10 percentage points: use the existing warning yellow.
- `Over pace` by more than 10 percentage points: use the existing danger red.
- The bar's existing remaining-quota color behavior stays unchanged; pace color
  is applied to the marker and pace label only.

This separation prevents a low remaining balance near the natural end of the
week from looking abnormal when it is still on pace.

## Layout

```text
Weekly quota                                      72% left
[======================|--------------------------]
                  expected 50%
Ahead 22%              Daily pace 14.3%     Reset 3d 12h
```

The exact label placement may collapse on narrow layouts:

- 8765 and 8766 use the marker inside the existing horizontal quota card.
- `/lite` uses a plain bordered bar and a short text row with no JavaScript.
- Windows replaces its current single quota bar with the same marker and adds
  one compact metadata line; the window remains materially shorter than the old
  two-row version.

## Data Boundaries

The shared snapshot keeps the weekly window's `windowMinutes`, `resetsAt`, and
`raw_reset_at` values. Pace calculations are implemented as small pure helpers
in Python for server-rendered and Windows views. Browser views may update the
marker once per refresh using the same formula.

If reset time or window duration is unavailable, the quota bar still renders,
but the marker and pace status show `Pace unavailable`. No inferred start time
is persisted.

## Testing

Pure calculation tests cover:

- start of a seven-day window: expected remaining 100%;
- midpoint at 3.5 days: expected remaining 50%;
- reset boundary: expected remaining 0%;
- Ahead, Over pace, and On pace labels;
- missing reset metadata returns an unavailable state;
- explicit API window duration takes precedence over the seven-day fallback.

After unit tests, verify both LaunchAgents, all local HTTP routes, the old-iPad
`/lite` response, Python compilation, and the Windows repository diff. The
Tkinter layout can be syntax-tested on macOS, but final pixel-level appearance
requires a Windows machine.
