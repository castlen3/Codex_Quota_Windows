#!/usr/bin/env python
"""
codex_quota_overlay.py — 桌面小浮窗，每 30 秒更新 Codex quota 剩餘量
"""
import json, os, ssl, urllib.request, urllib.error, threading, time
from datetime import datetime, timezone
import tkinter as tk

# Windows DPI awareness (optional, best-effort)
try:
    import ctypes
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass

# --- Config ---
AUTH_FILE = os.path.join(os.path.expanduser("~"), ".codex", "auth.json")
USAGE_URL = "https://chatgpt.com/backend-api/codex/usage"
REFRESH_SEC = 30
W = 380; H = 280; PAD = 18; BAR_H = 10
TOPMOST_DEFAULT = False

# Colors
BG     = "#10141c"
FG     = "#e5edf7"
DIM    = "#9aa4b2"
MUTED  = "#6f7b8c"
GREEN  = "#10b981"
YELLOW = "#f59e0b"
RED    = "#ef4444"
BLUE   = "#60a5fa"

# Fonts — positive point sizes for clarity
FONT_NUM   = ("Segoe UI", 16, "bold")
FONT_LBL   = ("Segoe UI", 9)
FONT_META  = ("Segoe UI", 8)
FONT_TITLE = ("Segoe UI", 10, "bold")
# -------------

def read_token():
    with open(AUTH_FILE, encoding="utf-8") as f:
        return json.load(f)["tokens"]["access_token"]

def fetch_usage(token):
    req = urllib.request.Request(USAGE_URL, headers={
        "Authorization": f"Bearer {token}",
        "User-Agent": "CodexCLI/0.137.0",
    })
    ctx = ssl.create_default_context()
    resp = urllib.request.urlopen(req, context=ctx, timeout=10)
    return json.loads(resp.read().decode())

def color_for(pct):
    if pct >= 50: return GREEN
    if pct >= 20: return YELLOW
    return RED

def fmt_pct(x):
    try:
        x = float(x)
        if abs(x - round(x)) < 0.05:
            return f"{round(x):.0f}%"
        return f"{x:.1f}%"
    except Exception:
        return "--"

class QuotaOverlay:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Codex Quota")
        self.root.configure(bg=BG)
        self.root.resizable(False, False)
        self.root.geometry(f"{W}x{H}")
        self.root.attributes("-topmost", TOPMOST_DEFAULT)

        # Right-click menu
        self.topmost_var = tk.BooleanVar(value=TOPMOST_DEFAULT)
        self.menu = tk.Menu(self.root, tearoff=0, bg=BG, fg=FG,
                            activebackground="#222a38", activeforeground=FG)
        self.menu.add_checkbutton(
            label="Always on top",
            variable=self.topmost_var,
            command=self.toggle_topmost,
        )
        self.menu.add_command(label="Refresh now", command=self.refresh)
        self.menu.add_separator()
        self.menu.add_command(label="Close", command=self.root.destroy)
        self.root.bind("<Button-3>", self.show_menu)

        # --- Header ---
        header = tk.Frame(self.root, bg=BG)
        header.pack(fill="x", padx=PAD, pady=(12, 0))
        self.status_dot = tk.Canvas(header, width=8, height=8, bg=BG, highlightthickness=0)
        self.status_dot.pack(side="left", padx=(0, 6))
        self.status_label = tk.Label(header, text="active", fg=DIM, bg=BG, font=FONT_META)
        self.status_label.pack(side="left")
        self.plan_badge = tk.Label(header, text="", fg=BLUE, bg="#1a2540",
                                   font=FONT_LBL, padx=10, pady=2)
        self.plan_badge.pack(side="right")

        # --- Primary bar ---
        self.pri_frame = tk.Frame(self.root, bg=BG)
        self.pri_frame.pack(fill="x", padx=PAD, pady=(12, 0))
        self.pri_label = tk.Label(self.pri_frame, text="5h remaining", fg=DIM, bg=BG,
                                  font=FONT_TITLE)
        self.pri_label.pack(anchor="w")
        self.pri_val = tk.Label(self.pri_frame, text="--", fg=FG, bg=BG, font=FONT_NUM)
        self.pri_val.pack(anchor="w", pady=(2, 4))
        self.pri_canvas = tk.Canvas(self.pri_frame, width=W-2*PAD, height=BAR_H,
                                    bg=BG, highlightthickness=0)
        self.pri_canvas.pack(fill="x")
        meta = tk.Frame(self.pri_frame, bg=BG)
        meta.pack(fill="x", pady=(4, 0))
        self.pri_used = tk.Label(meta, text="", fg=MUTED, bg=BG, font=FONT_META)
        self.pri_used.pack(side="left")
        self.pri_reset = tk.Label(meta, text="", fg=DIM, bg=BG, font=FONT_META)
        self.pri_reset.pack(side="right")

        # --- Secondary bar ---
        self.sec_frame = tk.Frame(self.root, bg=BG)
        self.sec_frame.pack(fill="x", padx=PAD, pady=(14, 0))
        self.sec_label = tk.Label(self.sec_frame, text="7d remaining", fg=DIM, bg=BG,
                                  font=FONT_TITLE)
        self.sec_label.pack(anchor="w")
        self.sec_val = tk.Label(self.sec_frame, text="--", fg=FG, bg=BG, font=FONT_NUM)
        self.sec_val.pack(anchor="w", pady=(2, 4))
        self.sec_canvas = tk.Canvas(self.sec_frame, width=W-2*PAD, height=BAR_H,
                                    bg=BG, highlightthickness=0)
        self.sec_canvas.pack(fill="x")
        meta2 = tk.Frame(self.sec_frame, bg=BG)
        meta2.pack(fill="x", pady=(4, 0))
        self.sec_used = tk.Label(meta2, text="", fg=MUTED, bg=BG, font=FONT_META)
        self.sec_used.pack(side="left")
        self.sec_reset = tk.Label(meta2, text="", fg=DIM, bg=BG, font=FONT_META)
        self.sec_reset.pack(side="right")

        # --- Footer ---
        self.footer = tk.Label(self.root, text="", fg="#3a4458", bg=BG, font=FONT_META)
        self.footer.pack(side="bottom", pady=(0, 10))

        # Position at top-left
        self._place_top_left()

        self.root.protocol("WM_DELETE_WINDOW", self.root.destroy)
        self.root.after(500, self.refresh)
        self.root.mainloop()

    def _place_top_left(self):
        margin_x = 24
        margin_y = 48
        self.root.geometry(f"{W}x{H}+{margin_x}+{margin_y}")

    def show_menu(self, event):
        self.menu.tk_popup(event.x_root, event.y_root)

    def toggle_topmost(self):
        self.root.attributes("-topmost", self.topmost_var.get())

    def draw_bar(self, canvas, pct, color, width):
        canvas.delete("all")
        h = BAR_H
        pct = max(0, min(100, float(pct)))
        # Track background
        canvas.create_rectangle(0, 0, width, h, fill="#222a38", outline="")
        if pct <= 0:
            return
        fill_w = max(2, int(pct / 100 * width))
        canvas.create_rectangle(0, 0, fill_w, h, fill=color, outline="")

    def refresh(self):
        t = threading.Thread(target=self._fetch, daemon=True)
        t.start()

    def _fetch(self):
        try:
            token = read_token()
            data = fetch_usage(token)
            rl = data.get("rate_limit", {})
            p = rl.get("primary_window", {})
            s = rl.get("secondary_window", {})

            pri_rem = 100 - p.get("used_percent", 0)
            sec_rem = 100 - s.get("used_percent", 0)
            now = datetime.now(timezone.utc)

            def t_left(epoch):
                if not epoch: return "--"
                dt = datetime.fromtimestamp(epoch, tz=timezone.utc)
                secs = (dt - now).total_seconds()
                h, m = int(secs // 3600), int((secs % 3600) // 60)
                return f"{h}h{m:02d}" if h > 0 else f"{m}m"

            pri_reset_str = t_left(p.get("reset_at"))
            sec_reset_str = t_left(s.get("reset_at"))
            limit_hit = rl.get("limit_reached", False)
            plan = data.get("plan_type", "?").upper()
            now_str = datetime.now().strftime("%H:%M:%S")

            self.root.after(0, lambda: self._apply(
                pri_rem, sec_rem, p.get("used_percent", 0), s.get("used_percent", 0),
                pri_reset_str, sec_reset_str, limit_hit, plan, now_str,
            ))
        except Exception:
            self.root.after(0, lambda: self._show_error())

        self.root.after(REFRESH_SEC * 1000, self.refresh)

    def _apply(self, pri_rem, sec_rem, pri_used, sec_used,
               pri_reset, sec_reset, limit_hit, plan, updated):
        # Status
        if limit_hit:
            self.status_dot.delete("all")
            self.status_dot.create_oval(1, 1, 7, 7, fill=RED, outline="")
            self.status_label.config(text="limited", fg=RED)
        else:
            self.status_dot.delete("all")
            self.status_dot.create_oval(1, 1, 7, 7, fill=GREEN, outline="")
            self.status_label.config(text="active", fg=DIM)

        self.plan_badge.config(text=plan)

        # Primary
        c1 = color_for(pri_rem)
        self.pri_val.config(text=fmt_pct(pri_rem), fg=c1)
        w = self.pri_canvas.winfo_width()
        if w < 10: w = W - 2*PAD
        self.draw_bar(self.pri_canvas, pri_rem, c1, w)
        self.pri_used.config(text=f"used {fmt_pct(pri_used)}")
        self.pri_reset.config(text=f"↻ {pri_reset}")

        # Secondary
        c2 = color_for(sec_rem)
        self.sec_val.config(text=fmt_pct(sec_rem), fg=c2)
        w = self.sec_canvas.winfo_width()
        if w < 10: w = W - 2*PAD
        self.draw_bar(self.sec_canvas, sec_rem, c2, w)
        self.sec_used.config(text=f"used {fmt_pct(sec_used)}")
        self.sec_reset.config(text=f"↻ {sec_reset}")

        self.footer.config(text=f"updated {updated} · {REFRESH_SEC}s")

    def _show_error(self):
        self.status_dot.delete("all")
        self.status_dot.create_oval(1, 1, 7, 7, fill=RED, outline="")
        self.status_label.config(text="offline", fg=RED)
        self.pri_val.config(text="--", fg=MUTED)
        self.sec_val.config(text="--", fg=MUTED)
        self.footer.config(text="retrying in 30s…")

if __name__ == "__main__":
    QuotaOverlay()
