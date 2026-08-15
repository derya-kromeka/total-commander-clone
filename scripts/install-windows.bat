@echo off
setlocal EnableExtensions EnableDelayedExpansion

REM ------------------------------------------------------------
REM Script: scripts/install-windows.bat
REM Purpose: Windows setup — find or install Python 3.8+, create
REM          .venv, install requirements.txt. Git credentials
REM          (remote URL, username, PAT) are configured in the app:
REM          Help → Git settings.
REM Usage:   scripts\install-windows.bat
REM          Then start with: scripts\run-windows.bat
REM ------------------------------------------------------------

cd /d "%~dp0.."

set "REQUIREMENTS=requirements.txt"
set "VENV=.venv"
set "PYEXE="
set "PYARG="

echo.
echo ============================================================
echo  Total Commander Clone - Windows install
echo ============================================================
echo  Project: %cd%
echo.

call :find_python
if defined PYEXE goto have_python

echo [INFO] Python 3.8+ not found. Attempting winget install...
where winget >nul 2>&1
if %ERRORLEVEL% NEQ 0 goto no_python
winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements
if errorlevel 1 (
  echo [WARN] winget Python install did not complete.
  goto no_python
)

REM New installs often land here; PATH may not be refreshed yet.
set "PATH=%LOCALAPPDATA%\Programs\Python\Python312;%LOCALAPPDATA%\Programs\Python\Python312\Scripts;%PATH%"
call :find_python
if defined PYEXE goto have_python

:no_python
echo [ERROR] Python 3.8+ not found.
echo         Install from https://www.python.org/downloads/windows/
echo         Enable "Add python.exe to PATH", then re-run this script.
echo         Or:  winget install -e --id Python.Python.3.12
exit /b 1

:have_python
echo [INFO] Using Python:
if "%PYARG%"=="-3" (
  py -3 --version
) else (
  "%PYEXE%" --version
)

if exist "%VENV%\Scripts\python.exe" (
  echo [INFO] Virtual environment already exists at %VENV% — refreshing packages.
) else (
  echo [INFO] Creating virtual environment at %VENV% ...
  if "%PYARG%"=="-3" (
    py -3 -m venv "%VENV%"
  ) else (
    "%PYEXE%" -m venv "%VENV%"
  )
  if errorlevel 1 (
    echo [ERROR] Failed to create virtual environment.
    echo         If this is a Microsoft Store Python stub, install Python from python.org.
    exit /b 1
  )
)

if not exist "%VENV%\Scripts\python.exe" (
  echo [ERROR] venv is missing %VENV%\Scripts\python.exe
  exit /b 1
)

echo [INFO] Ensuring pip...
"%VENV%\Scripts\python.exe" -m ensurepip --upgrade >nul 2>&1
"%VENV%\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 (
  echo [ERROR] Could not upgrade pip inside the venv.
  exit /b 1
)

if exist "%REQUIREMENTS%" (
  echo [INFO] Installing packages from %REQUIREMENTS% ...
  "%VENV%\Scripts\python.exe" -m pip install -r "%REQUIREMENTS%"
  if errorlevel 1 (
    echo [ERROR] pip install failed.
    exit /b 1
  )
) else (
  echo [WARN] No %REQUIREMENTS% found; skipping package install.
)

where git >nul 2>&1
if %ERRORLEVEL% EQU 0 (
  for /f "delims=" %%v in ('git --version 2^>nul') do echo [INFO] Git: %%v
) else (
  echo [WARN] Git is not on PATH. Pull/push from the app needs Git.
  echo         Install:  winget install --id Git.Git -e --source winget
  echo         Then close and reopen this window. You can still run the app now.
)

echo.
echo [INFO] Done.
echo         Start the app:  scripts\run-windows.bat
echo         Git remote / username / PAT:  Help → Git settings  (inside the app)
echo.
exit /b 0

REM ------------------------------------------------------------
REM Find a real Python 3.8+ (skip Microsoft Store stubs).
REM ------------------------------------------------------------
:find_python
set "PYEXE="
set "PYARG="

where py >nul 2>&1
if %ERRORLEVEL% EQU 0 (
  py -3 -c "import sys; raise SystemExit(0 if sys.version_info>=(3,8) else 1)" >nul 2>&1
  if not errorlevel 1 (
    set "PYEXE=py"
    set "PYARG=-3"
    exit /b 0
  )
)

where python3 >nul 2>&1
if %ERRORLEVEL% EQU 0 (
  call :check_python python3
  if not errorlevel 1 (
    set "PYEXE=python3"
    exit /b 0
  )
)

where python >nul 2>&1
if %ERRORLEVEL% EQU 0 (
  call :check_python python
  if not errorlevel 1 (
    set "PYEXE=python"
    exit /b 0
  )
)

for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python3*") do (
  if exist "%%~D\python.exe" (
    call :check_python "%%~D\python.exe"
    if not errorlevel 1 (
      set "PYEXE=%%~D\python.exe"
      exit /b 0
    )
  )
)
exit /b 1

:check_python
"%~1" -c "import sys; p=sys.executable.replace('\\','/'); raise SystemExit(0 if sys.version_info>=(3,8) and 'WindowsApps' not in p else 1)" >nul 2>&1
exit /b %ERRORLEVEL%
