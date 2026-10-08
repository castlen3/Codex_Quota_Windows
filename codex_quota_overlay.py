#!/usr/bin/env python
"""
Small desktop overlay for Codex quota status.

The ChatGPT/Codex usage endpoint can occasionally reject or time out even when
the network is fine, so this widget keeps the last good reading visible and
shows the real failure type instead of collapsing everything into "offline".
"""
import base64
import json
import os
import queue
import socket
import ssl
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

import tkinter as tk


import ctypes

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass

try:
    import msvcrt
except ImportError:
    msvcrt = None

try:
    import fcntl
except ImportError:
    fcntl = None


AUTH_FILE = os.path.join(os.path.expanduser("~"), ".codex", "auth.json")
TOKEN_REFRESH_URL = "https://auth.openai.com/oauth/token"
CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(SCRIPT_DIR, "codex_quota_overlay.log")
CACHE_FILE = os.path.join(SCRIPT_DIR, "codex_quota_overlay_cache.json")
LOCK_FILE = os.path.join(SCRIPT_DIR, ".overlay.lock")
USAGE_URLS = [
    "https://chatgpt.com/backend-api/wham/usage",
    "https://chatgpt.com/backend-api/codex/usage",
]
REFRESH_SEC = 30
MAX_BACKOFF_SEC = 300
LOG_MAX_BYTES = 200_000
LOG_KEEP_LINES = 1000
W = 430
H = 448
PAD = 20
BAR_H = 12
TICK_H = 20
WEEKLY_MIN_SECONDS = 6 * 24 * 60 * 60
FIVE_HOUR_MAX_SECONDS = 24 * 60 * 60
TOPMOST_DEFAULT = False


BG = "#0f1720"
PANEL = "#131d2a"
PANEL_2 = "#182434"
TRACK = "#253247"
FG = "#edf4ff"
DIM = "#9aa8ba"
MUTED = "#6f7f93"
GREEN = "#2dd4bf"
YELLOW = "#fbbf24"
RED = "#fb7185"
BLUE = "#93c5fd"
ORANGE = "#f59e0b"

FONT_TITLE = ("Segoe UI", 11, "bold")
FONT_NUM = ("Segoe UI", 24, "bold")
FONT_LABEL = ("Segoe UI", 9, "bold")
FONT_META = ("Segoe UI", 8)
FONT_FOOTER = ("Segoe UI", 8)


class QuotaError(Exception):
    def __init__(self, status, detail):
        super().__init__(detail)
        self.status = status
        self.detail = detail


def log_error(status, detail):
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        if os.path.exists(LOG_FILE) and os.path.getsize(LOG_FILE) > LOG_MAX_BYTES:
            # Keep the tail so a long-running widget does not grow forever.
            with open(LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
            kept = lines[-LOG_KEEP_LINES:]
            with open(LOG_FILE, "w", encoding="utf-8") as f:
                f.writelines(kept)
                f.write(f"[{stamp}] log trimmed to last {len(kept)} lines\n")
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{stamp}] {status}: {detail}\n")
    except Exception:
        pass


def is_jwt_expired(token, buffer_sec=300):
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return False
        payload_b64 = parts[1] + "=" * (-len(parts[1]) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_b64.encode("utf-8")))
        exp = payload.get("exp")
        if exp and isinstance(exp, (int, float)):
            return time.time() + buffer_sec >= exp
    except Exception:
        pass
    return False


_TOKEN_CACHE = {}


def read_auth_file():
    try:
        with open(AUTH_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError as exc:
        raise QuotaError("login missing", "Cannot find .codex/auth.json") from exc
    except Exception as exc:
        raise QuotaError("login error", f"Cannot read auth file: {exc}") from exc


def apply_token_response(current, token_resp, seen_refresh_token):
    """Merge a refresh response into the auth file contents.

    Returns (payload, access_token, should_write). If the Codex CLI refreshed the
    file while we were on the network, its values are newer, so the file wins and
    we skip the write instead of clobbering a fresher refresh token.
    """
    tokens = dict(current.get("tokens", {}))
    access_token = token_resp.get("access_token")

    if tokens.get("refresh_token") != seen_refresh_token:
        return None, (tokens.get("access_token") or access_token), False

    if access_token:
        tokens["access_token"] = access_token
    if "id_token" in token_resp:
        tokens["id_token"] = token_resp["id_token"]
    if "refresh_token" in token_resp:
        tokens["refresh_token"] = token_resp["refresh_token"]

    current["tokens"] = tokens
    current["last_refresh"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    return current, access_token, True


def refresh_access_token():
    auth_data = read_auth_file()
    tokens = auth_data.get("tokens", {})
    refresh_token = tokens.get("refresh_token")
    if not refresh_token:
        raise QuotaError("login missing", "No refresh_token in auth.json")

    payload = {
        "grant_type": "refresh_token",
        "client_id": CLIENT_ID,
        "refresh_token": refresh_token,
    }
    req = urllib.request.Request(
        TOKEN_REFRESH_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
            token_resp = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = ""
        try:
            body = exc.read().decode(errors="replace")[:180].replace("\n", " ")
        except Exception:
            pass
        raise QuotaError(f"refresh {exc.code}", body or "Token refresh rejected") from exc
    except Exception as exc:
        raise QuotaError("refresh failed", str(exc)) from exc

    new_access_token = token_resp.get("access_token")
    if not new_access_token:
        raise QuotaError("refresh failed", "No access_token in refresh response")

    # Re-read before writing so a concurrent Codex CLI write is not overwritten.
    try:
        current = read_auth_file()
    except QuotaError as exc:
        log_error("save auth skipped", str(exc))
        _TOKEN_CACHE["access_token"] = new_access_token
        return new_access_token

    write_payload, chosen_token, should_write = apply_token_response(
        current, token_resp, refresh_token
    )
    if should_write:
        try:
            tmp_file = AUTH_FILE + ".tmp"
            with open(tmp_file, "w", encoding="utf-8") as f:
                json.dump(write_payload, f, indent=2)
            os.replace(tmp_file, AUTH_FILE)
        except Exception as exc:
            log_error("save auth failed", str(exc))
    else:
        log_error("auth file changed", "skipped write; another writer updated auth.json")

    _TOKEN_CACHE["access_token"] = chosen_token
    return chosen_token


def read_token(force_refresh=False):
    cached = _TOKEN_CACHE.get("access_token")
    if cached and not force_refresh and not is_jwt_expired(cached):
        return cached

    token = read_auth_file().get("tokens", {}).get("access_token")
    if not token:
        raise QuotaError("login missing", "No access_token in auth.json")
    if force_refresh or is_jwt_expired(token):
        return refresh_access_token()

    _TOKEN_CACHE["access_token"] = token
    return token


def fetch_usage_from_url(token, url):
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "User-Agent": "codex-cli",
        },
    )
    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        body = ""
        try:
            body = exc.read().decode(errors="replace")[:180].replace("\n", " ")
        except Exception:
            pass
        if exc.code in (401, 403):
            raise QuotaError(f"blocked {exc.code}", body or "Auth rejected") from exc
        raise QuotaError(f"http {exc.code}", body or "HTTP error") from exc
    except (TimeoutError, socket.timeout) as exc:
        raise QuotaError("timeout", "Request timed out") from exc
    except urllib.error.URLError as exc:
        reason = getattr(exc, "reason", exc)
        raise QuotaError("network error", str(reason)) from exc
    except json.JSONDecodeError as exc:
        raise QuotaError("bad response", "Usage endpoint did not return JSON") from exc
    except Exception as exc:
        raise QuotaError("read failed", str(exc)) from exc


def fetch_usage(token):
    errors = []
    refreshed = False
    for url in USAGE_URLS:
        try:
            data = fetch_usage_from_url(token, url)
            data["_source_url"] = url
            return data
        except QuotaError as exc:
            if not refreshed and ("401" in exc.status or "403" in exc.status or "blocked" in exc.status):
                try:
                    token = refresh_access_token()
                    refreshed = True
                    data = fetch_usage_from_url(token, url)
                    data["_source_url"] = url
                    return data
                except QuotaError as ref_exc:
                    errors.append(f"{url}: {ref_exc.status}")
                    last_error = ref_exc
                    continue
            errors.append(f"{url}: {exc.status}")
            last_error = exc
    detail = "; ".join(errors)
    raise QuotaError(last_error.status, detail or last_error.detail)


def next_delay(streak, base=REFRESH_SEC, cap=MAX_BACKOFF_SEC):
    """Seconds to wait before the next refresh; backs off on consecutive errors."""
    if streak <= 0:
        return base
    return min(cap, base * (2 ** streak))


def color_for(pct):
    if pct >= 50:
        return GREEN
    if pct >= 20:
        return YELLOW
    return RED


def fmt_pct(value):
    try:
        value = float(value)
    except Exception:
        return "--"
    if abs(value - round(value)) < 0.05:
        return f"{round(value):.0f}%"
    return f"{value:.1f}%"


def clamp_pct(value):
    try:
        return max(0.0, min(100.0, float(value)))
    except Exception:
        return 0.0


def quota_pace(window, now_epoch=None):
    """Compare actual remaining quota with an even-use pace for the window."""
    reset_at = window.get("reset_at")
    if reset_at is None:
        return None

    try:
        window_seconds = max(1.0, float(window.get("limit_window_seconds") or 604800))
        now = time.time() if now_epoch is None else float(now_epoch)
        remaining_seconds = max(0.0, min(window_seconds, float(reset_at) - now))
        used = clamp_pct(window.get("used_percent", 0))
    except (TypeError, ValueError):
        return None

    expected = remaining_seconds / window_seconds * 100
    delta = (100 - used) - expected
    if abs(delta) < 1:
        status = "on_pace"
    elif delta > 0:
        status = "ahead"
    else:
        status = "over"

    return {
        "expected_remaining": round(expected, 1),
        "delta": round(delta, 1),
        "status": status,
        "daily_percent": round(86400 / window_seconds * 100, 1),
    }


def window_seconds(window):
    try:
        return float(window.get("limit_window_seconds") or 0)
    except (AttributeError, TypeError, ValueError):
        return 0.0


def window_data(window, now):
    used = clamp_pct(window.get("used_percent", 0))
    reset_at = window.get("reset_at")
    return {
        "remaining": 100 - used,
        "used": used,
        # Raw fields are kept so a cached snapshot can be recomputed on render
        # instead of showing the countdown/pace frozen at save time.
        "reset_at": reset_at,
        "reset": time_left(reset_at, now),
        "pace": quota_pace(window),
        "seconds": window_seconds(window),
    }


def display_fields(data, now):
    """Recompute renderable fields from raw values so a cached row is not stale."""
    reset_at = data.get("reset_at")
    if reset_at:
        pace = quota_pace({
            "used_percent": data.get("used", 0),
            "limit_window_seconds": data.get("seconds", 0),
            "reset_at": reset_at,
        }, now_epoch=now.timestamp()) or data.get("pace")
        return {"reset": time_left(reset_at, now), "pace": pace}
    # Legacy cache rows only stored display strings.
    return {"reset": data.get("reset") or "--", "pace": data.get("pace")}


def pace_text(pace):
    if not pace:
        return "Pace unavailable"
    delta = round(abs(pace.get("delta", 0)))
    if pace.get("status") == "ahead":
        return f"Ahead {delta}%"
    if pace.get("status") == "over":
        return f"Over pace {delta}%"
    return "On pace"


def time_left(epoch, now):
    if not epoch:
        return "--"
    reset = datetime.fromtimestamp(epoch, tz=timezone.utc)
    secs = max(0, int((reset - now).total_seconds()))
    days = secs // 86400
    hours = (secs % 86400) // 3600
    mins = (secs % 3600) // 60
    if days:
        return f"{days}d {hours}h"
    if hours:
        return f"{hours}h {mins:02d}m"
    return f"{mins}m"


def build_snapshot(data):
    rl = data.get("rate_limit", {})
    now = datetime.now(timezone.utc)
    windows = [
        window
        for window in (rl.get("primary_window"), rl.get("secondary_window"))
        if isinstance(window, dict) and window
    ]

    five_hour = None
    weekly = None
    for window in windows:
        seconds = window_seconds(window)
        if seconds and seconds < WEEKLY_MIN_SECONDS and seconds <= FIVE_HOUR_MAX_SECONDS:
            if five_hour is None or seconds < window_seconds(five_hour):
                five_hour = window
        elif seconds >= WEEKLY_MIN_SECONDS:
            if weekly is None or seconds > window_seconds(weekly):
                weekly = window

    if weekly is None:
        # No 7d window: fall back to the largest window so the widget still works.
        if not windows:
            raise QuotaError("bad response", "Usage response has no quota window")
        weekly = max(windows, key=window_seconds)
        if weekly is five_hour:
            five_hour = None  # don't show the same window in both rows

    return {
        "plan": str(data.get("plan_type") or "?").upper(),
        "limit_reached": bool(rl.get("limit_reached", False)),
        "five_hour": window_data(five_hour, now) if five_hour else None,
        "weekly": window_data(weekly, now),
        "updated": datetime.now().strftime("%H:%M:%S"),
        "source": "wham" if "wham" in data.get("_source_url", "") else "codex",
    }


_last_cache_signature = None


def cache_signature(snapshot):
    """The cache-relevant fields, excluding display-only values such as the clock."""

    def row(values):
        if not values:
            return None
        return (values.get("used"), values.get("reset_at"), values.get("seconds"))

    return (
        snapshot.get("plan"),
        snapshot.get("limit_reached"),
        snapshot.get("source"),
        row(snapshot.get("five_hour")),
        row(snapshot.get("weekly")),
    )


def load_cached_snapshot():
    global _last_cache_signature
    try:
        with open(CACHE_FILE, encoding="utf-8") as f:
            snapshot = json.load(f)
        # The old weekly-only format stored a quota_mode marker; the current
        # snapshot shape is enough on its own, so a cache file written without
        # that field still loads.
        if isinstance(snapshot, dict) and isinstance(snapshot.get("weekly"), dict):
            _last_cache_signature = cache_signature(snapshot)
            return snapshot
    except Exception:
        pass
    return None


def save_cached_snapshot(snapshot):
    global _last_cache_signature
    signature = cache_signature(snapshot)
    if signature == _last_cache_signature:
        # The quota itself did not change, so there is nothing to rewrite.
        return
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(snapshot, f, indent=2)
    except Exception:
        return
    _last_cache_signature = signature


_lock_fd = None


def _try_lock(fd):
    """Take a non-blocking exclusive lock on the first byte.

    Returns True when locked, False when another instance holds it, and None when
    no OS-level lock is available.
    """
    if msvcrt:
        try:
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            return True
        except OSError:
            return False
    if fcntl:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except OSError:
            return False
    return None


def _unlock(fd):
    if msvcrt:
        try:
            msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
        except Exception:
            pass
    elif fcntl:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        except Exception:
            pass


def acquire_instance_lock():
    """Hold an exclusive OS lock so a second widget cannot start.

    The OS releases the lock when the process exits, so a crashed instance does
    not leave a stale lock behind. The lock is deliberately not PID-based: on
    Windows os.kill(pid, 0) is TerminateProcess, not a liveness check.
    """
    global _lock_fd
    try:
        # O_RDWR (not append) so the lock is always taken on the same byte range.
        _lock_fd = os.open(LOCK_FILE, os.O_RDWR | os.O_CREAT)
    except Exception:
        # No writable lock: run anyway rather than refuse to start.
        return True

    if _try_lock(_lock_fd) is False:
        os.close(_lock_fd)
        _lock_fd = None
        return False

    try:
        os.lseek(_lock_fd, 0, os.SEEK_SET)
        os.write(_lock_fd, str(os.getpid()).encode("utf-8"))
    except Exception:
        pass
    return True


def release_instance_lock():
    global _lock_fd
    if _lock_fd is None:
        return
    _unlock(_lock_fd)
    try:
        os.close(_lock_fd)
    except Exception:
        pass
    try:
        os.remove(LOCK_FILE)
    except Exception:
        pass
    _lock_fd = None


class QuotaOverlay:
    def __init__(self):
        self.last_snapshot = load_cached_snapshot()
        self.fetching = False
        self.error_streak = 0
        self._first_map_done = False
        # Background threads only write to this queue; Tk is touched from the
        # main thread by _drain_events, because Tcl/Tk is not thread-safe.
        self.events = queue.Queue()

        self.root = tk.Tk()
        self.root.title("Codex Quota")
        self.root.configure(bg=BG)
        self.root.resizable(False, False)
        self.root.geometry(f"{W}x{H}")
        self.root.attributes("-topmost", TOPMOST_DEFAULT)

        self.topmost_var = tk.BooleanVar(value=TOPMOST_DEFAULT)
        self.menu = tk.Menu(
            self.root,
            tearoff=0,
            bg=PANEL,
            fg=FG,
            activebackground=PANEL_2,
            activeforeground=FG,
        )
        self.menu.add_checkbutton(
            label="Always on top",
            variable=self.topmost_var,
            command=self.toggle_topmost,
        )
        self.menu.add_command(label="Refresh now", command=self.refresh)
        self.menu.add_command(label="Open log folder", command=self.open_log_folder)
        self.menu.add_separator()
        self.menu.add_command(label="Close", command=self.root.destroy)
        self.root.bind("<Button-3>", self.show_menu)
        self.root.bind("<Map>", self._on_map)

        self.card = tk.Frame(self.root, bg=PANEL, bd=0, highlightthickness=1,
                             highlightbackground="#263246")
        self.card.pack(fill="both", expand=True, padx=10, pady=10)

        self._build_header()
        self._build_window_rows()
        self._build_footer()
        self._place_top_left()

        if self.last_snapshot:
            self._apply(self.last_snapshot, cached=True)

        self.root.protocol("WM_DELETE_WINDOW", self.root.destroy)
        self.root.after(100, self._drain_events)
        self.root.after(350, self.refresh)
        self.root.mainloop()

    def _build_header(self):
        header = tk.Frame(self.card, bg=PANEL)
        header.pack(fill="x", padx=PAD, pady=(16, 8))

        left = tk.Frame(header, bg=PANEL)
        left.pack(side="left")
        tk.Label(left, text="Codex Quota", fg=FG, bg=PANEL, font=FONT_TITLE).pack(anchor="w")

        status = tk.Frame(left, bg=PANEL)
        status.pack(anchor="w", pady=(3, 0))
        self.status_dot = tk.Canvas(status, width=9, height=9, bg=PANEL, highlightthickness=0)
        self.status_dot.pack(side="left", padx=(0, 7))
        self.status_label = tk.Label(status, text="loading", fg=DIM, bg=PANEL, font=FONT_META)
        self.status_label.pack(side="left")

        self.plan_badge = tk.Label(
            header,
            text="--",
            fg=BLUE,
            bg="#1d3151",
            font=FONT_LABEL,
            padx=12,
            pady=4,
        )
        self.plan_badge.pack(side="right")

    def _build_window_rows(self):
        self.five_hour = self._quota_row("5h quota", "five_hour", top_pad=16)
        self.weekly = self._quota_row("Weekly quota", "weekly", top_pad=14)

    def _quota_row(self, title, name, top_pad=12):
        row = tk.Frame(self.card, bg=PANEL)
        row.pack(fill="x", padx=PAD, pady=(top_pad, 0))

        top = tk.Frame(row, bg=PANEL)
        top.pack(fill="x")
        tk.Label(top, text=title.upper(), fg=DIM, bg=PANEL, font=FONT_LABEL).pack(side="left")
        reset = tk.Label(top, text="resets --", fg=MUTED, bg=PANEL, font=FONT_META)
        reset.pack(side="right")

        val = tk.Label(row, text="--", fg=FG, bg=PANEL, font=FONT_NUM)
        val.pack(anchor="w", pady=(2, 2))

        canvas = tk.Canvas(row, width=W - 2 * PAD - 20, height=TICK_H, bg=PANEL,
                           highlightthickness=0)
        canvas.pack(fill="x")

        meta = tk.Frame(row, bg=PANEL)
        meta.pack(fill="x", pady=(5, 0))
        pace = tk.Label(meta, text="Pace unavailable", fg=MUTED, bg=PANEL, font=FONT_META)
        pace.pack(side="left")
        if name == "weekly":
            daily = tk.Label(meta, text="Daily pace --", fg=MUTED, bg=PANEL, font=FONT_META)
            daily.pack(side="right")
        else:
            daily = None

        return {
            "name": name,
            "value": val,
            "canvas": canvas,
            "reset": reset,
            "pace": pace,
            "daily": daily,
        }

    def _build_footer(self):
        footer = tk.Frame(self.card, bg=PANEL)
        footer.pack(side="bottom", fill="x", padx=PAD, pady=(8, 14))
        self.footer = tk.Label(footer, text="starting...", fg=MUTED, bg=PANEL, font=FONT_FOOTER)
        self.footer.pack(side="left")
        self.next_refresh = tk.Label(footer, text=f"every {REFRESH_SEC}s", fg=MUTED,
                                     bg=PANEL, font=FONT_FOOTER)
        self.next_refresh.pack(side="right")

    def _place_top_left(self):
        self.root.geometry(f"{W}x{H}+24+48")

    def show_menu(self, event):
        self.menu.tk_popup(event.x_root, event.y_root)

    def _on_map(self, event):
        # Canvas widths are unknown until the window is mapped, so the first
        # paint falls back to a constant. Redraw once the real width is known.
        if self._first_map_done or not self.last_snapshot:
            return
        self._first_map_done = True
        self._apply(self.last_snapshot, cached=True)

    def toggle_topmost(self):
        self.root.attributes("-topmost", self.topmost_var.get())

    def open_log_folder(self):
        try:
            os.startfile(SCRIPT_DIR)
        except Exception:
            pass

    def draw_dot(self, color):
        self.status_dot.delete("all")
        self.status_dot.create_oval(1, 1, 8, 8, fill=color, outline="")

    def draw_bar(self, canvas, pct, color, pace=None):
        canvas.delete("all")
        width = canvas.winfo_width()
        if width < 20:
            width = W - 2 * PAD - 20
        height = canvas.winfo_height()
        if height < 10:
            height = TICK_H
        bar_top = (height - BAR_H) // 2
        pct = clamp_pct(pct)
        fill_w = int(pct / 100 * width)
        canvas.create_rectangle(0, bar_top, width, bar_top + BAR_H, fill=TRACK, outline="")
        if fill_w > 0:
            canvas.create_rectangle(0, bar_top, max(3, fill_w), bar_top + BAR_H, fill=color, outline="")
        if pace:
            # Vertical "should be here" tick: full canvas height with a dark
            # halo so it reads clearly against both the fill and the track.
            expected = clamp_pct(pace.get("expected_remaining", 0))
            marker_x = max(2, min(width - 3, int(expected / 100 * width)))
            marker_color = FG
            if pace.get("status") == "ahead":
                marker_color = GREEN
            elif pace.get("status") == "over":
                marker_color = RED if pace.get("delta", 0) < -10 else YELLOW
            canvas.create_rectangle(marker_x - 2, 0, marker_x + 3, height, fill="#0b1119", outline="")
            canvas.create_rectangle(marker_x - 1, 0, marker_x + 2, height, fill=marker_color, outline="")

    def refresh(self):
        if self.fetching:
            return
        self.fetching = True
        self.footer.config(text="refreshing...")
        try:
            threading.Thread(target=self._fetch, daemon=True).start()
        except Exception as exc:
            self.fetching = False
            log_error("thread start failed", str(exc))
            self.error_streak += 1
            self._show_error("thread failed")
            self._schedule_next_refresh()

    def _fetch(self):
        try:
            token = read_token()
            snapshot = build_snapshot(fetch_usage(token))
            self.events.put(("apply", snapshot, False))
        except QuotaError as exc:
            log_error(exc.status, exc.detail)
            self.events.put(("error", exc.status))
        except Exception as exc:
            detail = str(exc) or exc.__class__.__name__
            log_error("unexpected", detail)
            self.events.put(("error", "read failed"))
        # Worker threads only queue events here; Tk calls happen in _drain_events.
        self.events.put(("finish", None))

    def _drain_events(self):
        while True:
            try:
                event = self.events.get_nowait()
            except queue.Empty:
                break
            kind = event[0]
            if kind == "apply":
                self.error_streak = 0
                self._apply(event[1], cached=event[2])
            elif kind == "error":
                self.error_streak += 1
                self._show_error(event[1])
            elif kind == "finish":
                self._finish_fetch()
                self._schedule_next_refresh()
        self.root.after(200, self._drain_events)

    def _schedule_next_refresh(self):
        delay = next_delay(self.error_streak)
        self.next_refresh.config(
            text=f"every {delay}s" if delay == REFRESH_SEC else f"backoff {delay}s"
        )
        # Scheduled from the main thread only, so the auto-refresh chain survives
        # a failed thread start or a fetch that produced no usable result.
        self.root.after(delay * 1000, self.refresh)

    def _finish_fetch(self):
        self.fetching = False

    def _apply(self, snapshot, cached=False):
        self.last_snapshot = snapshot
        if not cached:
            save_cached_snapshot(snapshot)
        self.plan_badge.config(text=snapshot["plan"])

        if snapshot["limit_reached"]:
            self.draw_dot(RED)
            self.status_label.config(text="limited", fg=RED)
        else:
            self.draw_dot(GREEN)
            self.status_label.config(text="cached" if cached else "live", fg=DIM)

        self._apply_row(self.five_hour, snapshot.get("five_hour"))
        self._apply_row(self.weekly, snapshot["weekly"])
        prefix = "cached" if cached else "updated"
        source = snapshot.get("source", "api")
        self.footer.config(text=f"{prefix} {snapshot['updated']} via {source}")

    def _apply_row(self, row, data):
        if not data:
            row["value"].config(text="--", fg=MUTED)
            row["reset"].config(text="--")
            row["pace"].config(text="not in response", fg=MUTED)
            if row["daily"]:
                row["daily"].config(text="")
            row["canvas"].delete("all")
            return

        remaining = data["remaining"]
        color = color_for(remaining)

        # Recompute from raw fields so a cached row shows the current countdown
        # and pace, not the values frozen when the cache was written.
        display = display_fields(data, datetime.now(timezone.utc))
        pace = display["pace"]

        row["value"].config(text=fmt_pct(remaining), fg=color)
        row["reset"].config(text=f"resets in {display['reset']}")
        pace_color = GREEN
        if pace and pace.get("status") == "over":
            pace_color = RED if pace.get("delta", 0) < -10 else YELLOW
        row["pace"].config(text=pace_text(pace), fg=pace_color if pace else MUTED)
        if row["daily"]:
            daily = pace.get("daily_percent") if pace else "--"
            row["daily"].config(text=f"Daily pace {daily}%")
        self.draw_bar(row["canvas"], remaining, color, pace)

    def _show_error(self, status):
        display = status
        color = ORANGE
        if "401" in status or "403" in status or status.startswith("login"):
            color = RED
        elif status == "timeout":
            color = YELLOW

        self.draw_dot(color)
        self.status_label.config(text=display, fg=color)

        if self.last_snapshot:
            self.footer.config(text=f"last good {self.last_snapshot['updated']} - retrying")
        else:
            self.footer.config(text=f"{display} - retrying")


def notify_already_running():
    if not hasattr(ctypes, "windll"):
        return
    try:
        # MessageBoxW is stdcall with four parameters; passing three would leave
        # the stack unbalanced and can crash the process.
        ctypes.windll.user32.MessageBoxW(
            None,
            "Codex Quota Overlay is already running.",
            "Codex Quota",
            0x40,  # MB_ICONINFORMATION | MB_OK
        )
    except Exception:
        pass


if __name__ == "__main__":
    if not acquire_instance_lock():
        log_error("already running", "another overlay instance holds the lock")
        notify_already_running()
        raise SystemExit(0)
    try:
        QuotaOverlay()
    except Exception as exc:
        # pythonw has no console, so a startup failure is otherwise invisible.
        log_error("startup failed", str(exc) or exc.__class__.__name__)
        raise
    finally:
        release_instance_lock()
