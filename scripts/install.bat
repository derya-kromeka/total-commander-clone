@echo off
REM ------------------------------------------------------------
REM Script: scripts/install.bat
REM Purpose: Compatibility wrapper. Prefer scripts\install-windows.bat
REM ------------------------------------------------------------
call "%~dp0install-windows.bat" %*
exit /b %ERRORLEVEL%
