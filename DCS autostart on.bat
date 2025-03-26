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

REM Check if the start command is already in the file
findstr /c:"dofile('!CURRENT_DIR!\\src\\main.lua')" "%TARGET_FILE%" >nul
if errorlevel 1 (
    REM Add the start command to the file
    echo dofile('!CURRENT_DIR!\\src\\main.lua')>> "%TARGET_FILE%"
    echo Autostart enabled successfully.
) else (
    echo Autostart is already enabled.
)

REM Update settings.cfg
set "SETTINGS_FILE=!CURRENT_DIR!\src\settings.cfg"
powershell -Command "(Get-Content '!SETTINGS_FILE!') -replace 'Auto_Start = False', 'Auto_Start = True' | Set-Content '!SETTINGS_FILE!'"

echo.
echo Configuration complete.
pause