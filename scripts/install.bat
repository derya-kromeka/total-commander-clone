@echo off
setlocal EnableExtensions

REM ------------------------------------------------------------
REM Script: scripts/install.bat
REM Purpose: Create project .venv (Windows cmd), install requirements.
REM          Use this from Command Prompt or PowerShell: scripts\install.bat
REM          For Git Bash / WSL, prefer: bash scripts/install.sh
REM ------------------------------------------------------------

cd /d "%~dp0.."

set "REQUIREMENTS=requirements.txt"
set "VENV=.venv"

set "PYEXE="
set "PYARG="

where py >nul 2>&1
if %ERRORLEVEL% EQU 0 (
  set "PYEXE=py"
  set "PYARG=-3"
  goto have_python
)
where python3 >nul 2>&1
if %ERRORLEVEL% EQU 0 (
  set "PYEXE=python3"
  goto have_python
)
where python >nul 2>&1
if %ERRORLEVEL% EQU 0 (
  set "PYEXE=python"
  goto have_python
)

echo [ERROR] Python 3 not found. Install from https://www.python.org/downloads/
echo         Then add Python to PATH and re-run this script.
exit /b 1

:have_python
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
    exit /b 1
  )
)

"%VENV%\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 exit /b 1

if exist "%REQUIREMENTS%" (
  echo [INFO] Installing packages from %REQUIREMENTS% ...
  "%VENV%\Scripts\pip.exe" install -r "%REQUIREMENTS%"
  if errorlevel 1 (
    echo [ERROR] pip install failed.
    exit /b 1
  )
) else (
  echo [WARN] No %REQUIREMENTS% found; skipping package install.
)

echo [INFO] Done. Start the app with: scripts\run.bat
exit /b 0
