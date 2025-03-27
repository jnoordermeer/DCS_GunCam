@echo off
echo ========================================
echo    DCS GunCam Autostart Disable
echo ========================================
echo.

REM Check if running as administrator
net session >nul 2>&1
if errorlevel 1 (
    echo This script requires administrator privileges.
    echo Please run as administrator.
    pause
    exit /b 1
)

REM Get DCS World Saved Games path
set "DCS_PATH=%USERPROFILE%\Saved Games"
if not exist "%DCS_PATH%" (
    echo Error: Could not find Saved Games folder.
    pause
    exit /b 1
)

REM Look for DCS folders (excluding release server)
set "FOUND_DCS=0"
if exist "%DCS_PATH%\DCS.openbeta\Scripts" (
    set "DCS_FOLDER=%DCS_PATH%\DCS.openbeta"
    set "FOUND_DCS=1"
) else if exist "%DCS_PATH%\DCS\Scripts" (
    set "DCS_FOLDER=%DCS_PATH%\DCS"
    set "FOUND_DCS=1"
)

if "%FOUND_DCS%"=="0" (
    echo Error: Could not find DCS World installation in Saved Games.
    echo Please make sure DCS World is installed.
    pause
    exit /b 1
)

REM Remove the hook script if it exists
if exist "%DCS_FOLDER%\Scripts\Hooks\GunCam_by_ProtoDutch.lua" (
    del "%DCS_FOLDER%\Scripts\Hooks\GunCam_by_ProtoDutch.lua"
    echo Autostart disabled successfully!
) else (
    echo Autostart was not enabled.
)

echo.
echo DCS GunCam will no longer start automatically with DCS World.
echo.
pause