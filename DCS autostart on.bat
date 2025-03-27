@echo off
setlocal enabledelayedexpansion

REM Get the current directory
set "CURRENT_DIR=%~dp0"
REM Remove trailing backslash
set "CURRENT_DIR=!CURRENT_DIR:~0,-1!"

REM Set the target file path
set "TARGET_FILE=%LOCALAPPDATA%\DCS.openbeta\Config\autoexec.cfg"

REM Create directory if it doesn't exist
if not exist "%LOCALAPPDATA%\DCS.openbeta\Config" (
    mkdir "%LOCALAPPDATA%\DCS.openbeta\Config"
)

REM Check if autoexec.cfg exists, if not create it
if not exist "%TARGET_FILE%" (
    echo -- DCS World autoexec.cfg> "%TARGET_FILE%"
)

REM Create the Hooks directory if it doesn't exist
if not exist "%LOCALAPPDATA%\DCS.openbeta\Scripts\Hooks" (
    mkdir "%LOCALAPPDATA%\DCS.openbeta\Scripts\Hooks"
)

REM Create the GunCam_By_ProtoDutch.lua with the new content
(
echo local batPath = os.getenv("APPDATA") .. "\\GunCam_By_Protodutch\\GunCam.bat"
echo log.write('DCS_GunCam', log.DEBUG, 'Auto-starting GunCam...')
echo os.execute('start "" /B "' .. batPath .. '"')
) > "%LOCALAPPDATA%\DCS.openbeta\Scripts\Hooks\GunCam_By_ProtoDutch.lua"

REM Update settings.cfg
set "SETTINGS_FILE=!CURRENT_DIR!\src\settings.cfg"
powershell -Command "(Get-Content '!SETTINGS_FILE!') -replace 'Auto_Start = False', 'Auto_Start = True' | Set-Content '!SETTINGS_FILE!'"

echo.
echo Configuration complete.
echo DCS GunCam will now start automatically with DCS World.
pause