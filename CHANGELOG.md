# Changelog

## Unreleased

- Switched the primary usage endpoint to `https://chatgpt.com/backend-api/wham/usage`.
- Kept `https://chatgpt.com/backend-api/codex/usage` as a fallback endpoint.
- Changed the usage request User-Agent to `codex-cli` to avoid `403` responses seen with newer request fingerprints.
- Added clearer error states for auth, network, timeout, HTTP, and blocked responses.
- Added local last-good cache support so the widget can keep showing the previous successful quota reading after a failed refresh.
- Added local diagnostic logging to `codex_quota_overlay.log`.
- Enlarged the widget window and adjusted spacing so the footer is not clipped.
- Rewrote English and Traditional Chinese README files without private local information.
