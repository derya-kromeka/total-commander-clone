@echo off
REM Copy updated git-*.cmd / git-*.ps1 from sibling faceswap-on-rust into this repo.
setlocal
set "DEST=%~dp0"
set "SRC=%~dp0..\..\faceswap-on-rust\scripts"
if not exist "%SRC%\git-sync.ps1" (
    echo ERROR: Source not found: %SRC%
    echo Copy scripts\git-sync.ps1 manually from the machine that has the latest repo.
    pause
    exit /b 1
)
for %%f in (git-sync.ps1 git-account.ps1 git-pull.cmd git-push.cmd git-sync.cmd git-config-account.cmd install.ps1 install.bat) do (
    if exist "%SRC%\%%f" copy /Y "%SRC%\%%f" "%DEST%\%%f" >nul
)
if exist "%~dp0..\git-pull.cmd" copy /Y "%~dp0..\..\faceswap-on-rust\git-pull.cmd" "%~dp0..\git-pull.cmd" >nul 2>&1
echo Updated git scripts in %DEST%
pause
