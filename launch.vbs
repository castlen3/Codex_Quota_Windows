' Codex Quota Overlay Launcher
' Double-click to run. No console window.
' Uses the local Python 3.12 install if present, otherwise falls back to PATH.

Set ws = CreateObject("Wscript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
ws.CurrentDirectory = fso.GetParentFolderName(WScript.ScriptFullName)

pythonw = ws.ExpandEnvironmentStrings("%LocalAppData%") & "\Programs\Python\Python312\pythonw.exe"
python = ws.ExpandEnvironmentStrings("%LocalAppData%") & "\Programs\Python\Python312\python.exe"

On Error Resume Next
If fso.FileExists(pythonw) Then
    ws.Run """" & pythonw & """ codex_quota_overlay.py", 0, False
ElseIf fso.FileExists(python) Then
    ws.Run """" & python & """ codex_quota_overlay.py", 0, False
Else
    ws.Run "pythonw codex_quota_overlay.py", 0, False
    If Err.Number <> 0 Then
        Err.Clear
        ws.Run "python codex_quota_overlay.py", 0, False
    End If
End If
On Error Goto 0
