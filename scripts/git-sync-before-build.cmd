@echo off
REM Compare APP_VERSION to remote and push/pull before a build (see build.bat).
setlocal
cd /d "%~dp0.."
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0git-sync.ps1" -Action BuildSync %*
exit /b %ERRORLEVEL%
