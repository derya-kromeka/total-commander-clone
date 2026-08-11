Option Explicit

' ------------------------------------------------------------
' Script: scripts/run-hidden.vbs
' Purpose: Launch run.bat without showing a terminal window.
' run.bat sets CWD to project root (parent of scripts\).
' ------------------------------------------------------------

Dim fso
Dim shell
Dim script_dir
Dim bat_path
Dim cmd

Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")

script_dir = fso.GetParentFolderName(WScript.ScriptFullName)
bat_path = script_dir & "\run.bat"

If Not fso.FileExists(bat_path) Then
    MsgBox "Could not find run.bat at: " & vbCrLf & bat_path, vbCritical, "Launcher Error"
    WScript.Quit 1
End If

' Run hidden (window style 0), do not wait (False).
cmd = "cmd /c """ & bat_path & """"
shell.Run cmd, 0, False
