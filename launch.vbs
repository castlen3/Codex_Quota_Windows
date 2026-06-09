' Codex Quota Overlay — Launcher
' Double-click to run. No console window.
' Requires: Python 3 with tkinter (included by default on Windows).

Set ws = CreateObject("Wscript.Shell")
ws.CurrentDirectory = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)

' Try pythonw first (no console), fall back to python
On Error Resume Next
ws.Run "pythonw codex_quota_overlay.py", 0, False
If Err.Number <> 0 Then
    Err.Clear
    ws.Run "python codex_quota_overlay.py", 0, False
End If
On Error Goto 0
