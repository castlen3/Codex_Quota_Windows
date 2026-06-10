#!/usr/bin/env python
"""
Small desktop overlay for Codex quota status.

The ChatGPT/Codex usage endpoint can occasionally reject or time out even when
the network is fine, so this widget keeps the last good reading visible and
shows the real failure type instead of collapsing everything into "offline".
"""
import json
import os
import ssl
import threading
import urllib.error
import urllib.request
from datetime import datetime, timezone

import tkinter as tk


try:
    import ctypes
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass


AUTH_FILE = os.path.join(os.path.expanduser("~"), ".codex", "auth.json")
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(SCRIPT_DIR, "codex_quota_overlay.log")
CACHE_FILE = os.path.join(SCRIPT_DIR, "codex_quota_overlay_cache.json")
USAGE_URLS = [
    "https://chatgpt.com/backend-api/wham/usage",
    "https://chatgpt.com/backend-api/codex/usage",
]
REFRESH_SEC = 30
W = 430
H = 350
PAD = 20
BAR_H = 12
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
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{stamp}] {status}: {detail}\n")
    except Exception:
        pass


def read_token():
    try:
        with open(AUTH_FILE, encoding="utf-8") as f:
            token = json.load(f).get("tokens", {}).get("access_token")
    except FileNotFoundError as exc:
        raise QuotaError("login missing", "Cannot find .codex/auth.json") from exc
    except Exception as exc:
        raise QuotaError("login error", f"Cannot read auth file: {exc}") from exc

    if not token:
        raise QuotaError("login missing", "No access_token in auth.json")
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
    except TimeoutError as exc:
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
    for url in USAGE_URLS:
        try:
            data = fetch_usage_from_url(token, url)
            data["_source_url"] = url
            return data
        except QuotaError as exc:
            errors.append(f"{url}: {exc.status}")
            last_error = exc
    detail = "; ".join(errors)
    raise QuotaError(last_error.status, detail or last_error.detail)


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
    primary = rl.get("primary_window", {})
    secondary = rl.get("secondary_window", {})
    now = datetime.now(timezone.utc)

    pri_used = clamp_pct(primary.get("used_percent", 0))
    sec_used = clamp_pct(secondary.get("used_percent", 0))

    return {
        "plan": str(data.get("plan_type") or "?").upper(),
        "limit_reached": bool(rl.get("limit_reached", False)),
        "primary": {
            "remaining": 100 - pri_used,
            "used": pri_used,
            "reset": time_left(primary.get("reset_at"), now),
        },
        "secondary": {
            "remaining": 100 - sec_used,
            "used": sec_used,
            "reset": time_left(secondary.get("reset_at"), now),
        },
        "updated": datetime.now().strftime("%H:%M:%S"),
        "source": "wham" if "wham" in data.get("_source_url", "") else "codex",
    }


def load_cached_snapshot():
    try:
        with open(CACHE_FILE, encoding="utf-8") as f:
            snapshot = json.load(f)
        if isinstance(snapshot, dict) and "primary" in snapshot and "secondary" in snapshot:
            return snapshot
    except Exception:
        pass
    return None


def save_cached_snapshot(snapshot):
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(snapshot, f, indent=2)
    except Exception:
        pass


class QuotaOverlay:
    def __init__(self):
        self.last_snapshot = load_cached_snapshot()
        self.fetching = False

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
        self.primary = self._quota_row("5h window", "primary", top_pad=12)
        self.secondary = self._quota_row("7d window", "secondary", top_pad=16)

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

        canvas = tk.Canvas(row, width=W - 2 * PAD - 20, height=BAR_H, bg=PANEL,
                           highlightthickness=0)
        canvas.pack(fill="x")

        meta = tk.Frame(row, bg=PANEL)
        meta.pack(fill="x", pady=(5, 0))
        used = tk.Label(meta, text="used --", fg=MUTED, bg=PANEL, font=FONT_META)
        used.pack(side="left")
        remaining = tk.Label(meta, text="remaining", fg=MUTED, bg=PANEL, font=FONT_META)
        remaining.pack(side="right")

        return {
            "name": name,
            "value": val,
            "canvas": canvas,
            "reset": reset,
            "used": used,
            "remaining": remaining,
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

    def draw_bar(self, canvas, pct, color):
        canvas.delete("all")
        width = canvas.winfo_width()
        if width < 20:
            width = W - 2 * PAD - 20
        pct = clamp_pct(pct)
        fill_w = int(pct / 100 * width)
        canvas.create_rectangle(0, 0, width, BAR_H, fill=TRACK, outline="")
        if fill_w > 0:
            canvas.create_rectangle(0, 0, max(3, fill_w), BAR_H, fill=color, outline="")

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
            self._show_error("thread failed")

    def _fetch(self):
        try:
            token = read_token()
            snapshot = build_snapshot(fetch_usage(token))
            self.root.after(0, lambda: self._apply(snapshot))
        except QuotaError as exc:
            log_error(exc.status, exc.detail)
            status = exc.status
            self.root.after(0, lambda status=status: self._show_error(status))
        except Exception as exc:
            detail = str(exc) or exc.__class__.__name__
            log_error("unexpected", detail)
            self.root.after(0, lambda: self._show_error("read failed"))
        finally:
            self.root.after(0, self._finish_fetch)
            self.root.after(REFRESH_SEC * 1000, self.refresh)

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

        self._apply_row(self.primary, snapshot["primary"])
        self._apply_row(self.secondary, snapshot["secondary"])
        prefix = "cached" if cached else "updated"
        source = snapshot.get("source", "api")
        self.footer.config(text=f"{prefix} {snapshot['updated']} via {source}")

    def _apply_row(self, row, data):
        remaining = data["remaining"]
        color = color_for(remaining)
        row["value"].config(text=fmt_pct(remaining), fg=color)
        row["reset"].config(text=f"resets in {data['reset']}")
        row["used"].config(text=f"used {fmt_pct(data['used'])}")
        row["remaining"].config(text="remaining")
        self.draw_bar(row["canvas"], remaining, color)

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


if __name__ == "__main__":
    QuotaOverlay()
