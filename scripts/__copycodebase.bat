@echo off
REM Project root: parent of scripts\ (same folder as main.py; portable).
REM So __copycodebase.py and __copycodebase.json next to main.py resolve correctly.
cd /d "%~dp0.."

REM Run the Python script and keep the window open for feedback
python __copycodebase.py
