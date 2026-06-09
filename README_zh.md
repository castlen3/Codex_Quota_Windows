[English](README.md) | [繁體中文](README_zh.md)

# Codex Quota Overlay

即時桌面小工具，顯示你的 OpenAI Codex / ChatGPT 用量配額。  
直接從官方 `chatgpt.com/backend-api/codex/usage` 端點取得資料。

![screenshot](screenshot.png)

## 功能特色

- **即時用量條** — 5 小時與 7 天滾動視窗
- **顏色警示** — 綠色（≥50%）、黃色（20–49%）、紅色（<20%）
- **自動刷新** 每 30 秒更新一次
- **置頂切換** 右鍵選單可切換 Always on top
- **零依賴** 純 Python 標準庫（tkinter, json, urllib, threading）
- **Windows 原生** 小視窗，不開瀏覽器、不吃 Electron

## 系統需求

- **Windows 10/11**
- **Python 3.9+** 含 tkinter（Windows 安裝 Python 時預設已包含）
- **Codex Desktop** 已安裝並透過 ChatGPT 登入

工具會從 `%USERPROFILE%\.codex\auth.json` 讀取你的 access token — 就是 Codex Desktop 內部使用的同一個檔案。憑證不會被儲存或傳送到其他地方。

## 快速開始

1. 確認 [Codex Desktop](https://codex.openai.com/) 已安裝且已登入
2. 雙擊 `launch.vbs`

一個小視窗會出現在螢幕左上角。右鍵點擊可開啟選單。

## 手動執行

```bash
python codex_quota_overlay.py
```

不顯示命令列視窗：

```bash
pythonw codex_quota_overlay.py
```

## 運作原理

```
auth.json (本機)  →  access_token
                            ↓
chatgpt.com/backend-api/codex/usage  →  rate_limit JSON
                            ↓
                    tkinter 小視窗（每 30 秒自動刷新）
```

API 回傳的資料格式：

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

## 隱私

- 你的 access token 只從本機 `auth.json` 讀取，僅用於向 `chatgpt.com/backend-api/codex/usage` 發出單次 API 呼叫。
- 不會記錄、儲存或傳送任何資料到其他地方。
- 全部程式碼約 250 行，5 分鐘就能審查完畢。

## 授權

MIT
