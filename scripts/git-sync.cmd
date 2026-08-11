@echo off
REM Launcher for git-sync.ps1 (push / pull with interactive setup)
setlocal
cd /d "%~dp0.."
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0git-sync.ps1" %*
exit /b %ERRORLEVEL%
