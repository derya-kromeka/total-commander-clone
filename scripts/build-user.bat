@echo off
setlocal EnableExtensions

REM ------------------------------------------------------------
REM Script: scripts/build-user.bat
REM Purpose: Compatibility wrapper. Builds the current sources
REM          with PyInstaller. Git push/pull is handled in the app.
REM ------------------------------------------------------------

call "%~dp0build.bat" skip-git %*
exit /b %ERRORLEVEL%
