@echo off
setlocal EnableExtensions

REM ------------------------------------------------------------
REM Script: scripts/build-user.bat
REM Purpose: Build the current local sources into a standalone .exe
REM          with NO Git sync, push, pull, or GitHub account.
REM
REM Use this for everyday rebuilds on a user PC.
REM Developers who want version sync with GitHub should use build.bat.
REM ------------------------------------------------------------

cd /d "%~dp0.."

echo.
echo ============================================================
echo  Total Commander Clone - User build ^(no Git^)
echo ============================================================
echo  Project: %cd%
echo.

call "%~dp0build.bat" skip-git %*
exit /b %ERRORLEVEL%
