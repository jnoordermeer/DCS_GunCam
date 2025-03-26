@echo off
echo ========================================
echo    DCS GunCam Installer v1.4.1
echo ========================================
echo.

REM Check if Python is installed
python --version > nul 2>&1
if errorlevel 1 (
    echo Python is not installed! Please install Python 3.x first.
    echo You can download it from: https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)

echo [1/4] Checking Python installation... OK
echo [2/4] Creating video directory...

REM Create default video directory
mkdir "C:\Users\Public\Videos\DCS_GunCam" 2> nul
if errorlevel 1 (
    echo Warning: Could not create video directory. Please create it manually.
) else (
    echo Video directory created successfully.
)

echo [3/4] Installing required packages...
echo.

REM Install required packages
python -m pip install --upgrade pip
pip install -r requirements.txt

if errorlevel 1 (
    echo.
    echo Error: Package installation failed!
    echo Please try running the installer as administrator.
    pause
    exit /b 1
)

echo.
echo [4/4] Setup completed successfully!
echo.
echo ========================================
echo    Installation Complete!
echo ========================================
echo.
echo You can now:
echo 1. Start DCS World
echo 2. Run start.bat to launch DCS GunCam
echo.
echo For help and updates, visit:
echo https://www.protodutch.com
echo.
pause