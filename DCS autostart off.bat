@echo off
setlocal enabledelayedexpansion

REM Set the target file path
set "TARGET_FILE=%LOCALAPPDATA%\DCS.openbeta\Config\autoexec.cfg"

REM Check if autoexec.cfg exists
if exist "%TARGET_FILE%" (
    REM Create a temporary file
    set "TEMP_FILE=%TEMP%\autoexec.tmp"
    
    REM Copy all lines except the one containing our command
    findstr /v /c:"dofile('" "%TARGET_FILE%" > "%TEMP_FILE%"
    
    REM Replace the original file
    move /y "%TEMP_FILE%" "%TARGET_FILE%" >nul
    
    echo Autostart disabled successfully.
) else (
    echo No autoexec.cfg found. Autostart was not enabled.
)

REM Update settings.cfg
set "SETTINGS_FILE=%~dp0src\settings.cfg"
powershell -Command "(Get-Content '!SETTINGS_FILE!') -replace 'Auto_Start = True', 'Auto_Start = False' | Set-Content '!SETTINGS_FILE!'"

echo.
echo Configuration complete.
pause