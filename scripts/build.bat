@echo off
setlocal EnableExtensions

REM ------------------------------------------------------------
REM Script: scripts/build.bat
REM Purpose: Build standalone .exe with PyInstaller for correct
REM          taskbar icon and launch behavior.
REM Project root: parent of this scripts\ folder (portable; no absolute paths).
REM ------------------------------------------------------------

cd /d "%~dp0.."

set "ICON=file-explorer.ico"
set "SCRIPT=main.py"
set "PYTHON_EXE="
set "PYTHON_ARGS="

if not exist "%SCRIPT%" (
    echo [ERROR] Could not find "%SCRIPT%" in:
    echo         %cd%
    exit /b 1
)

if not exist "%ICON%" (
    echo [ERROR] Could not find "%ICON%". Icon is required for the build.
    exit /b 1
)

where py >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    set "PYTHON_EXE=py"
    set "PYTHON_ARGS=-3"
) else (
    where python >nul 2>&1
    if %ERRORLEVEL% EQU 0 (
        set "PYTHON_EXE=python"
    ) else (
        where python3 >nul 2>&1
        if %ERRORLEVEL% EQU 0 (
            set "PYTHON_EXE=python3"
        )
    )
)

if "%PYTHON_EXE%"=="" (
    echo [ERROR] Python was not found.
    exit /b 1
)

echo [INFO] Installing dependencies (requirements.txt)...
%PYTHON_EXE% %PYTHON_ARGS% -m pip install -r requirements.txt --quiet
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Could not install requirements.
    exit /b 1
)

REM Kill any running TotalCommanderClone.exe so dist folder can be cleaned
taskkill /IM TotalCommanderClone.exe /F >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo [INFO] Stopped running TotalCommanderClone.exe
    timeout /t 2 /nobreak >nul
)

echo [INFO] Building standalone .exe (TotalCommanderClone.spec)...
%PYTHON_EXE% %PYTHON_ARGS% -m PyInstaller --noconfirm --clean TotalCommanderClone.spec

if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Build failed.
    exit /b 1
)

echo.
echo [INFO] Build complete. Output: dist\TotalCommanderClone\TotalCommanderClone.exe
echo [INFO] Settings are stored in %%APPDATA%%\TotalCommanderClone (persists across rebuilds).
exit /b 0
