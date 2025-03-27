@echo off
setlocal enabledelayedexpansion

REM Set the target paths
set "HOOK_FILE=%LOCALAPPDATA%\DCS.openbeta\Scripts\Hooks\GunCam_By_ProtoDutch.lua"

REM Remove the hook script if it exists
if exist "%HOOK_FILE%" (
    del "%HOOK_FILE%"
    echo Hook script removed successfully.
) else (
    echo Hook script was not found. Autostart was not enabled.
)

REM Update settings.cfg
set "SETTINGS_FILE=%~dp0src\settings.cfg"
powershell -Command "(Get-Content '!SETTINGS_FILE!') -replace 'Auto_Start = True', 'Auto_Start = False' | Set-Content '!SETTINGS_FILE!'"

echo.
echo Configuration complete.
echo DCS GunCam will no longer start automatically with DCS World.
pause