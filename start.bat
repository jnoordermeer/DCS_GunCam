@echo off
echo Starting DCS GunCam...
echo.

REM Change to script directory
cd /d "%~dp0"

REM Check if Python is installed
python --version > nul 2>&1
if errorlevel 1 (
    echo Error: Python is not installed or not in PATH!
    echo Please run install.bat first.
    pause
    exit /b 1
)

REM Check if main.py exists
if not exist "src\main.py" (
    echo Error: Could not find src\main.py
    echo Please make sure all files are in the correct location.
    pause
    exit /b 1
)

REM Start the application
python src/main.py

REM If Python exits with an error
if errorlevel 1 (
    echo.
    echo Error: Application crashed!
    echo Please check the log file for details.
    pause
)