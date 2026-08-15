@echo off
REM ------------------------------------------------------------
REM Script: scripts/run.bat
REM Purpose: Compatibility wrapper. Prefer scripts\run-windows.bat
REM ------------------------------------------------------------
call "%~dp0run-windows.bat" %*
exit /b %ERRORLEVEL%
