@echo off
title TubeDownloader Pro Launcher
cd /d "%~dp0"

echo ==========================================================
echo  [*] Starting TubeDownloader Pro...
echo ==========================================================

where python >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Python is not installed or not in PATH!
    echo Please install Python 3.10+ from https://www.python.org/
    echo Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)

python -c "import yt_dlp, customtkinter, PIL, mutagen" >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [*] Installing required packages...
    python -m pip install --upgrade pip
    python -m pip install -r requirements.txt
)

python main.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ==========================================================
    echo [ERROR] TubeDownloader Pro exited unexpectedly.
    echo Check crash.log for details.
    echo ==========================================================
    pause
)
