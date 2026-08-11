@echo off
cd /d "%~dp0.."
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0git-sync.ps1" -Action Push %*
exit /b %ERRORLEVEL%
