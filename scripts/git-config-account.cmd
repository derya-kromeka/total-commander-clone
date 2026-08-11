@echo off
cd /d "%~dp0.."
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0git-account.ps1" %*
exit /b %ERRORLEVEL%
