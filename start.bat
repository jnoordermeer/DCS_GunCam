@echo off
setlocal

REM Check if Python is installed
python --version > nul 2>&1
if errorlevel 1 (
    echo Error: Python is not installed or not in PATH!
    echo Please install Python from python.org
    pause
    exit /b 1
)

REM Check if required packages are installed
python -c "import sys, pygame, win32gui, cv2, numpy, mss, PyQt6" > nul 2>&1
if errorlevel 1 (
    echo Error: Some required packages are missing!
    echo Please run install.bat as administrator
    pause
    exit /b 1
)

REM Start DCS GunCam
cd /d "%~dp0"
python src/main.py
pause