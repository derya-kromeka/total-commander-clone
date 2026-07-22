@echo off
setlocal EnableExtensions

REM ------------------------------------------------------------
REM Script: scripts/update-and-rebuild.bat
REM Purpose: Called from the app when the user accepts a Git update.
REM          Waits for TotalCommanderClone.exe to exit, pulls the
REM          latest code, rebuilds the standalone exe, then relaunches.
REM ------------------------------------------------------------

cd /d "%~dp0.."

set "APP_EXE=TotalCommanderClone.exe"
set "DIST_EXE=dist\TotalCommanderClone\TotalCommanderClone.exe"
set "BRANCH="
set "REMOTE=origin"
set "PUBLIC_URL=https://github.com/derya-kromeka/total-commander-clone.git"

echo.
echo ============================================================
echo  Total Commander Clone - Update and rebuild
echo ============================================================
echo  Project: %cd%
echo.

echo [INFO] Waiting for %APP_EXE% to exit...
set /a "_wait=0"
:wait_app
call :is_app_running
if errorlevel 1 goto app_stopped
set /a "_wait+=1"
if %_wait% GEQ 60 (
    echo [WARN] App still running after ~2 minutes. Trying to stop it...
    taskkill /IM %APP_EXE% /F >nul 2>&1
    ping 127.0.0.1 -n 3 >nul
    goto app_stopped
)
ping 127.0.0.1 -n 3 >nul
goto wait_app

:app_stopped
echo [INFO] App is not running. Continuing...
echo.

where git >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Git is not installed or not on PATH.
    echo         Install Git for Windows, then run this script again.
    goto fail
)

for /f "delims=" %%b in ('git branch --show-current 2^>nul') do set "BRANCH=%%b"
if "%BRANCH%"=="" set "BRANCH=main"

git remote get-url %REMOTE% >nul 2>&1
if errorlevel 1 (
    echo [INFO] Adding public remote %REMOTE% -^> %PUBLIC_URL%
    git remote add %REMOTE% "%PUBLIC_URL%"
    if errorlevel 1 (
        echo [ERROR] Could not add remote %REMOTE%.
        goto fail
    )
)

echo [INFO] Fetching %REMOTE%/%BRANCH% ^(public HTTPS, no login^)...
git fetch "%REMOTE%" "%BRANCH%"
if errorlevel 1 (
    echo [ERROR] git fetch failed.
    echo         Public clone URL: %PUBLIC_URL%
    echo         Check network access, then retry or run scripts\git-pull.cmd
    goto fail
)

echo [INFO] Merging %REMOTE%/%BRANCH% into local branch...
git merge --no-edit "%REMOTE%/%BRANCH%"
if errorlevel 1 (
    echo [ERROR] git merge failed ^(conflicts or local changes?^).
    echo         Resolve conflicts, then run: scripts\build.bat skip-git
    goto fail
)

echo.
echo [INFO] Building new executable ^(scripts\build.bat skip-git^)...
call "%~dp0build.bat" skip-git
if errorlevel 1 (
    echo [ERROR] Build failed. See messages above.
    goto fail
)

if not exist "%DIST_EXE%" (
    echo [ERROR] Build finished but exe not found:
    echo         %DIST_EXE%
    goto fail
)

echo.
echo [INFO] Starting updated app...
start "" "%DIST_EXE%"
echo [OK] Update complete.
exit /b 0

:fail
echo.
echo Update did not finish successfully.
pause
exit /b 1

REM ------------------------------------------------------------
:is_app_running
tasklist /FI "IMAGENAME eq %APP_EXE%" 2>nul | find /I "%APP_EXE%" >nul
if errorlevel 1 exit /b 1
exit /b 0
