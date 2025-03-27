@echo off
setlocal enabledelayedexpansion

REM Check for admin rights
net session >nul 2>&1
if errorlevel 1 (
    echo Error: This script requires administrator privileges.
    echo Please right-click and select "Run as administrator".
    pause
    exit /b 1
)

REM Get the current directory
set "INSTALL_DIR=%~dp0"
set "INSTALL_DIR=!INSTALL_DIR:~0,-1!"

echo ========================================
echo    DCS GunCam Installer
echo    Version 1.5
echo ========================================
echo.

REM Check if Python is installed
echo [1/8] Checking Python installation...
echo.

python --version > nul 2>&1
if errorlevel 1 (
    echo Error: Python is not installed or not in PATH!
    echo Please install Python from python.org
    echo Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)

echo Python installation found.
echo.

REM Create default video directory
echo [2/8] Creating video directory...
echo.

mkdir "C:\Users\Public\Videos\DCS_GunCam" 2> nul
if errorlevel 1 (
    echo Warning: Could not create video directory. Please create it manually.
) else (
    echo Video directory created successfully.
)

echo [3/8] Upgrading pip, setuptools, and wheel...
echo.

REM Upgrade base packages
python -m pip install --upgrade pip setuptools wheel
if errorlevel 1 (
    echo.
    echo Error: Failed to upgrade pip, setuptools, and wheel!
    echo Please try running the installer as administrator.
    pause
    exit /b 1
)

echo [4/8] Checking installed packages...
echo.

REM Get list of installed packages
for /f "tokens=1" %%i in ('python -m pip list') do (
    set "pkg_%%i=1"
)

REM Check and install required packages if missing
if not defined pkg_PyQt6 (
    python -m pip install PyQt6>=6.4.2
)

if not defined pkg_pygame (
    python -m pip install pygame>=2.5.2
)

if not defined pkg_pywin32 (
    python -m pip install pywin32>=306
)

if not defined pkg_opencv-python (
    python -m pip install opencv-python>=4.8.0.74
)

if not defined pkg_numpy (
    python -m pip install numpy>=1.24.3
)

if not defined pkg_mss (
    python -m pip install mss>=9.0.1
)

if not defined pkg_Pillow (
    python -m pip install Pillow>=10.0.0
)

echo [5/8] Creating shortcuts...
echo.

REM Create VBScript for shortcuts
set "VBS_FILE=%TEMP%\CreateShortcuts.vbs"
(
    echo Set objWSHShell = CreateObject^("WScript.Shell"^)
    echo strDesktop = objWSHShell.SpecialFolders^("Desktop"^)
    echo strStartMenu = objWSHShell.SpecialFolders^("Programs"^)
    echo strAppPath = "%INSTALL_DIR%"
    echo.
    echo ' Create Desktop shortcut
    echo Set objShortcut = objWSHShell.CreateShortcut^(strDesktop ^& "\DCS GunCam.lnk"^)
    echo objShortcut.TargetPath = strAppPath ^& "\GunCam.bat"
    echo objShortcut.WorkingDirectory = strAppPath
    echo objShortcut.IconLocation = strAppPath ^& "\src\ag_mouse_.ico"
    echo objShortcut.Description = "DCS World GunCam Recording Application"
    echo objShortcut.Save
    echo.
    echo ' Create Start Menu folder and shortcuts
    echo strFolder = strStartMenu ^& "\DCS GunCam"
    echo Set objFSO = CreateObject^("Scripting.FileSystemObject"^)
    echo If Not objFSO.FolderExists^(strFolder^) Then
    echo     objFSO.CreateFolder^(strFolder^)
    echo End If
    echo.
    echo ' Create Start Menu shortcut
    echo Set objShortcut = objWSHShell.CreateShortcut^(strFolder ^& "\DCS GunCam.lnk"^)
    echo objShortcut.TargetPath = strAppPath ^& "\GunCam.bat"
    echo objShortcut.WorkingDirectory = strAppPath
    echo objShortcut.IconLocation = strAppPath ^& "\src\ag_mouse_.ico"
    echo objShortcut.Description = "DCS World GunCam Recording Application"
    echo objShortcut.Save
    echo.
    echo ' Create Folder shortcut
    echo Set objShortcut = objWSHShell.CreateShortcut^(strFolder ^& "\Installation Folder.lnk"^)
    echo objShortcut.TargetPath = strAppPath
    echo objShortcut.IconLocation = strAppPath ^& "\src\ag_mouse_.ico"
    echo objShortcut.Save
) > "%VBS_FILE%"

REM Execute the VBScript
cscript //nologo "%VBS_FILE%"
del "%VBS_FILE%"

echo [6/8] Configure DCS World autostart...
echo.

set /p AUTOSTART="Would you like DCS GunCam to start automatically with DCS World? (Y/N): "
if /i "%AUTOSTART%"=="Y" (
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
    powershell -Command "(Get-Content '%INSTALL_DIR%\src\settings.cfg') -replace 'Auto_Start = False', 'Auto_Start = True' | Set-Content '%INSTALL_DIR%\src\settings.cfg'"
    echo Autostart enabled successfully.
) else (
    echo Autostart will not be enabled.
)

echo.
echo [7/8] Verifying installation...
python -c "import sys, pygame, win32gui, cv2, numpy, mss, PyQt6, PIL" > nul 2>&1
if errorlevel 1 (
    echo.
    echo Error: Package verification failed!
    echo Some packages may not have installed correctly.
    echo Please try running the installer again as administrator.
    pause
    exit /b 1
)

echo [8/8] Installation Summary
echo.
echo ========================================
echo    Installation Complete!
echo ========================================
echo.
echo Installation location: %INSTALL_DIR%
echo.
echo Shortcuts created:
echo - Desktop: DCS GunCam
echo - Start Menu: DCS GunCam
echo.
echo Before starting:
echo ---------------
echo 1. Configure your settings:
echo    - Gun Trigger (default: Button 0)
echo    - Canon Trigger (default: Button 1)
echo    - Rockets/Bomb Trigger (default: Button 5)
echo    - Pre-trigger duration in seconds (default: 6)
echo    - Post-trigger duration in seconds (default: 6)
echo    - Recording quality (default: Normal 1080p)
echo    - FPS (default: 30)
echo    - Pilot Name
echo    - Flight Unit
echo.
echo All settings are saved automatically.
echo.
echo Press any key to start DCS GunCam...
pause >nul

echo [9/9] Starting DCS GunCam...
start "" "%INSTALL_DIR%\GunCam.bat"
exit