# Weekly Quota Pace Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an expected weekly-usage marker and Ahead/Over pace status to the 8765, 8766, `/lite`, and Windows quota displays.

**Architecture:** The local Python quota normalizer computes deterministic pace metadata once and both web servers render it. The standalone Windows application implements the same pure calculation contract locally. Each UI keeps its existing visual language and adds one marker plus one compact metadata line.

**Tech Stack:** Python 3 standard library, `unittest`, server-rendered HTML/CSS/JavaScript, Tkinter, macOS LaunchAgents, Git/GitHub CLI.

## Global Constraints

- Daily pace is informational and fixed at 14.3%, not a separate allowance.
- Expected remaining is based on reset time divided by the API window duration, falling back to 604800 seconds.
- Deltas below 1 percentage point display `On pace`.
- Ahead/On pace uses green, over pace up to 10 points uses yellow, and over pace above 10 points uses red.
- Existing dark palettes, compact layouts, reset countdowns, and old-device `/lite` compatibility remain intact.
- Missing reset metadata leaves the actual quota visible and displays `Pace unavailable`.

---

### Task 1: Local Pace Data Model

**Files:**
- Modify: `/Users/castlen3/codex/tools/codex_quota_watch.py`
- Create: `/Users/castlen3/codex/tools/test_quota_pace.py`

**Interfaces:**
- Consumes: normalized weekly window dictionaries containing `usedPercent`, `windowMinutes`, and `raw_reset_at`.
- Produces: `quota_pace(window, now_epoch=None) -> dict | None` and a `pace` field inside the normalized weekly window.

- [ ] **Step 1: Write failing tests for start, midpoint, reset, status labels, and missing reset metadata**

```python
pace = quota_pace({"usedPercent": 28, "windowMinutes": 10080, "raw_reset_at": 1_604_800}, now_epoch=1_302_400)
self.assertEqual(pace["expectedRemaining"], 50.0)
self.assertEqual(pace["delta"], 22.0)
self.assertEqual(pace["status"], "ahead")
```

- [ ] **Step 2: Run `python3 -m unittest -v test_quota_pace.py` and verify failure because `quota_pace` is missing**
- [ ] **Step 3: Implement clamped expected remaining, rounded delta, `ahead`/`over`/`on_pace`, and unavailable behavior**
- [ ] **Step 4: Attach pace metadata to `weekly` in `build_snapshot` and run all local unit tests**

### Task 2: Local Web And Lite Views

**Files:**
- Modify: `/Users/castlen3/codex/tools/codex_quota_web.py`
- Modify: `/Users/castlen3/codex/tools/lmstudio_status_web.py`

**Interfaces:**
- Consumes: `weekly.pace.expectedRemaining`, `weekly.pace.delta`, `weekly.pace.status`, and `weekly.pace.dailyPercent`.
- Produces: an actual-remaining bar, expected-remaining marker, status label, daily pace label, and unchanged reset countdown.

- [ ] **Step 1: Add static HTML assertions that both modern pages contain pace marker/status hooks and `/lite` contains a server-rendered marker**
- [ ] **Step 2: Run the assertions before edits and verify they fail on missing hooks**
- [ ] **Step 3: Replace the 8765 circular gauge with a compact horizontal bar and marker while preserving status/plan badges**
- [ ] **Step 4: Add the marker and pace metadata row to the existing 8766 quota bar**
- [ ] **Step 5: Render a CSS-only marker and short pace line in `/lite` without JavaScript or modern CSS dependencies**
- [ ] **Step 6: Compile scripts, restart both LaunchAgents, and verify `/api`, `/`, and `/lite` on ports 8765 and 8766**

### Task 3: Windows Overlay And GitHub Publication

**Files:**
- Modify: `/Users/castlen3/codex/Codex_Quota_Windows/codex_quota_overlay.py`
- Modify: `/Users/castlen3/codex/Codex_Quota_Windows/test_codex_quota_overlay.py`
- Modify: `/Users/castlen3/codex/Codex_Quota_Windows/README.md`
- Modify: `/Users/castlen3/codex/Codex_Quota_Windows/README_zh.md`
- Modify: `/Users/castlen3/codex/Codex_Quota_Windows/CHANGELOG.md`

**Interfaces:**
- Consumes: raw weekly API window reset time and duration.
- Produces: `quota_pace(window, now=None)` metadata in `snapshot["weekly"]["pace"]` and a Tkinter canvas marker/status row.

- [ ] **Step 1: Add failing Windows tests matching the local midpoint, Ahead, Over pace, On pace, and unavailable cases**
- [ ] **Step 2: Run `python3 -m unittest -v test_codex_quota_overlay.py` and verify the new tests fail**
- [ ] **Step 3: Implement the pure pace helper and include its result in the weekly snapshot**
- [ ] **Step 4: Draw the expected marker on the Tkinter quota canvas and update the compact metadata line**
- [ ] **Step 5: Document the pace marker in both READMEs and changelog**
- [ ] **Step 6: Run unit tests, Python compilation, `git diff --check`, and inspect the final diff**
- [ ] **Step 7: Commit, push `agent/quota-pace-marker`, open a PR, merge it to `main`, and verify the remote merge commit**
