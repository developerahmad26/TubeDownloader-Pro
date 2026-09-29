@echo off
setlocal enabledelayedexpansion
title TubeDownloader Pro Launcher
cd /d "%~dp0"

echo ==========================================================
echo  [*] Starting TubeDownloader Pro...
echo ==========================================================

:: 1. Detect Python executable (python, py -3, or venv)
set "PY_CMD="

if exist "venv\Scripts\python.exe" (
    set "PY_CMD=venv\Scripts\python.exe"
    goto :PYTHON_FOUND
)

where python >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    set "PY_CMD=python"
    goto :PYTHON_FOUND
)

where py >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    set "PY_CMD=py -3"
    goto :PYTHON_FOUND
)

echo.
echo ==========================================================
echo [ERROR] Python is not installed or not in your system PATH!
echo Please install Python 3.10+ from https://www.python.org/
echo IMPORTANT: Check the box "Add Python to PATH" during setup.
echo ==========================================================
echo.
pause
exit /b 1

:PYTHON_FOUND
:: 2. Check and install missing dependencies
!PY_CMD! -c "import yt_dlp, customtkinter, PIL, mutagen" >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [*] Installing required packages...
    !PY_CMD! -m pip install --upgrade pip --quiet
    !PY_CMD! -m pip install -r requirements.txt
)

:: 3. Launch application
!PY_CMD! main.py
set "EXIT_CODE=%ERRORLEVEL%"

if %EXIT_CODE% NEQ 0 (
    echo.
    echo ==========================================================
    echo [ERROR] TubeDownloader Pro exited with code: %EXIT_CODE%
    if exist "crash.log" (
        echo Details from crash.log:
        echo ----------------------------------------------------------
        type "crash.log"
        echo ----------------------------------------------------------
    )
    echo ==========================================================
    echo.
    pause
)
