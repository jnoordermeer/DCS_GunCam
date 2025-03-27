@echo off
echo ========================================
echo    DCS GunCam Autostart Enable
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

echo Found DCS folder: %DCS_FOLDER%

REM Create Scripts folder if it doesn't exist
if not exist "%DCS_FOLDER%\Scripts" (
    mkdir "%DCS_FOLDER%\Scripts"
)

REM Create Hooks folder if it doesn't exist
if not exist "%DCS_FOLDER%\Scripts\Hooks" (
    mkdir "%DCS_FOLDER%\Scripts\Hooks"
)

REM Create the hook script
echo Creating hook script...

echo local batPath = os.getenv^(^"APPDATA^"^) .. "\\GunCam_By_Protodutch\\GunCam.bat" > "%DCS_FOLDER%\Scripts\Hooks\GunCam_by_ProtoDutch.lua"
echo log.write('DCS_GunCam', log.DEBUG, 'Auto-starting GunCam...') >> "%DCS_FOLDER%\Scripts\Hooks\GunCam_by_ProtoDutch.lua"
echo os.execute('start "" /B "' .. batPath .. '"') >> "%DCS_FOLDER%\Scripts\Hooks\GunCam_by_ProtoDutch.lua"


echo.
echo Autostart enabled successfully!
echo DCS GunCam will now start automatically when you launch a mission in DCS World.
echo.
echo Note: Make sure to run DCS World as administrator if you experience any issues.
echo.
pause