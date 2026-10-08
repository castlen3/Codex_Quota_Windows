# Codex Quota Overlay for Windows

[English](README.md) | [繁體中文](README_zh.md)

這是一個 Windows 桌面小工具，用來顯示 OpenAI Codex / ChatGPT 的 quota 使用狀態。

它會讀取本機 Codex OAuth token，也就是 `%USERPROFILE%\.codex\auth.json`，呼叫 ChatGPT usage endpoint，然後用小型 Tkinter 浮窗顯示目前的 5 小時與週額度。

## 這版更新

- 配合 Codex 恢復成雙額度（5 小時 + 週）的新版格式。
- 同一個視窗同時顯示兩條額度：5 小時在上、週額度在下。
- `primary_window` 視為 5 小時額度，`secondary_window` 視為週額度。
- 若 API 沒有回傳週額度，會 fallback 到最大的 window，且不會重複顯示同一個 window。
- 每條額度橫條加了一條全高度的 pace 直槓：顯示「此刻應該用掉多少」。
  - 綠色直槓 = 超前進度（用得比預期少）。
  - 白色直槓 = 剛好跟上進度。
  - 黃色/紅色直槓 = 落後進度（用得比預期多）。
- 5 小時那一列不顯示「每日 pace」標籤，因為 5 小時窗口沒有每日 pace 的概念。
- 優先使用 `https://chatgpt.com/backend-api/wham/usage`。
- `https://chatgpt.com/backend-api/codex/usage` 改為備援。
- User-Agent 改為 `codex-cli`，避免新版 Codex usage endpoint 在某些請求指紋下回傳 `403`。
- 狀態顯示更清楚，例如 `blocked 403`、`timeout`、`login missing`、`network error`。
- 如果更新失敗，會保留上一筆成功讀到的 quota，不會整個變成空白。
- 本機診斷訊息會寫入 `codex_quota_overlay.log`，超過 200 KB 後只保留最後 1000 行。
- 連續失敗會退避（30s → 60s → 120s → 240s → 300s），footer 會顯示目前間隔；成功讀取後回到 30s。
- 寫入 `auth.json` 前會先重讀，若 Codex CLI 在請求期間已更新檔案，就不會覆蓋它。
- 同時只會執行一個實例；第二次啟動會顯示提示後結束。
- 上一筆成功讀取結果會快取在 `codex_quota_overlay_cache.json`。
- `launch.vbs` 優先用本機 Python 3.12（`%LocalAppData%\Programs\Python\Python312`），找不到才 fallback 到 PATH。

## 功能

- 同一個視窗即時顯示 5 小時與週額度。
- 全高度 pace 直槓，一眼看出目前應該用掉多少。
- 一眼判斷目前是 `Ahead`、`On pace` 或 `Over pace`。
- 依剩餘比例用綠色、黃色、紅色顯示。
- 每 30 秒自動更新。
- 右鍵選單支援重新整理、永遠置頂、開啟 log 資料夾、關閉。
- 不需要第三方 Python 套件。
- Windows 原生小浮窗，不需要瀏覽器或 Electron。

## 需求

- Windows 10 或 Windows 11。
- Python 3.9+，需包含 Tkinter。
- Codex Desktop 或 Codex CLI 已用 ChatGPT 登入。

## 快速開始

1. 確認 Codex 已安裝並登入。
2. 雙擊 `launch.vbs`。
3. 在小工具上按右鍵可開啟選單。

## 手動執行

```powershell
python codex_quota_overlay.py
```

不顯示 console 視窗：

```powershell
pythonw codex_quota_overlay.py
```

## 運作方式

```text
%USERPROFILE%\.codex\auth.json
        -> access token
        -> chatgpt.com/backend-api/wham/usage
        -> rate_limit JSON
        -> Tkinter overlay
```

API 回傳格式大致如下：

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

`primary_window` 是 5 小時額度，`secondary_window` 是週額度。每條橫條上的全高度直槓代表：如果把用量平均分配在該窗口內，此刻理論上應剩下多少。這只是使用節奏提示，不是另一個上限；未使用的額度會保留到窗口重置為止。

## 隱私

- access token 只會從本機 Codex auth 檔讀取，並只送到 `chatgpt.com` 查詢 usage。
- 專案內不包含 token、帳號 email、個人路徑或 quota 快照。
- log 與 cache 等執行期間產生的檔案已加入 Git 忽略清單。

## 授權

MIT，見 [LICENSE](LICENSE)。
