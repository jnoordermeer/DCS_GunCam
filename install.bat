@echo off
echo ========================================
echo    DCS GunCam Installer v1.4.1
echo ========================================
echo.

echo [1/9] Checking Python version...
python --version > "%TEMP%\pyver.txt" 2>&1
if errorlevel 1 (
    echo Python is not installed!
    echo Please download and install Python 3.x from:
    echo https://www.python.org/downloads/
    echo.
    echo Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)
set /p PYVER=<"%TEMP%\pyver.txt"
echo Found: %PYVER%
del "%TEMP%\pyver.txt"

echo [2/9] Checking pip installation...
python -m pip --version > "%TEMP%\pipver.txt" 2>&1
if errorlevel 1 (
    echo pip is not installed!
    echo Please run the following command to install pip:
    echo python -m ensurepip --default-pip
    echo.
    echo Or download get-pip.py from:
    echo https://bootstrap.pypa.io/get-pip.py
    pause
    exit /b 1
)
set /p PIPVER=<"%TEMP%\pipver.txt"
echo Found: %PIPVER%
del "%TEMP%\pipver.txt"

echo [3/9] Checking required packages...
echo.

REM Define minimum versions
set "REQ_PYQT6=6.6.1"
set "REQ_PYGAME=2.5.2"
set "REQ_PYWIN32=310"
set "REQ_OPENCV=4.9.0.80"
set "REQ_NUMPY=1.26.4"
set "REQ_MSS=9.0.1"

REM First ensure setuptools and wheel are installed
echo Installing base requirements...
python -m pip install --upgrade pip setuptools wheel
if errorlevel 1 (
    echo.
    echo Error: Failed to upgrade pip, setuptools, and wheel!
    echo Please try running the installer as administrator.
    pause
    exit /b 1
)

echo Installing/Upgrading required packages...
echo.

REM Check if pygame is already installed
python -c "import pygame" >nul 2>&1
if errorlevel 1 (
    echo Installing pygame...
    python -m pip install --only-binary pygame "pygame>=%REQ_PYGAME%"
    if errorlevel 1 goto INSTALL_ERROR
) else (
    echo pygame is already installed, skipping...
)

REM Install other packages one by one
echo Installing PyQt6...
python -m pip install "PyQt6>=%REQ_PYQT6%" "PyQt6-Qt6>=%REQ_PYQT6%" "PyQt6-sip>=13.6.0"
if errorlevel 1 goto INSTALL_ERROR

echo Installing pywin32...
python -m pip install "pywin32>=%REQ_PYWIN32%"
if errorlevel 1 goto INSTALL_ERROR

echo Installing opencv-python...
python -m pip install "opencv-python>=%REQ_OPENCV%"
if errorlevel 1 goto INSTALL_ERROR

echo Installing numpy...
python -m pip install "numpy>=%REQ_NUMPY%"
if errorlevel 1 goto INSTALL_ERROR

echo Installing mss...
python -m pip install "mss>=%REQ_MSS%"
if errorlevel 1 goto INSTALL_ERROR

echo Installing Pillow...
python -m pip install "Pillow>=10.0.0"
if errorlevel 1 goto INSTALL_ERROR

goto INSTALL_SUCCESS

:INSTALL_ERROR
echo.
echo Error: Package installation failed!
echo Please try running the installer as administrator.
pause
exit /b 1

:INSTALL_SUCCESS
echo [4/9] Installing application files...
set "INSTALL_DIR=%APPDATA%\GunCam_By_Protodutch"
if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"

REM Copy all files except settings.ini if it exists
if exist "%INSTALL_DIR%\settings.ini" (
    echo Preserving existing settings.ini...
    xcopy /E /I /Y /EXCLUDE:settings.ini "%~dp0*" "%INSTALL_DIR%\"
) else (
    xcopy /E /I /Y "%~dp0*" "%INSTALL_DIR%\"
)

if errorlevel 1 (
    echo Error: Failed to copy files to %INSTALL_DIR%
    echo Please make sure you have write permissions.
    pause
    exit /b 1
)

echo [5/9] Creating desktop shortcut...
echo.

REM Create VBScript for desktop shortcut
echo Set oWS = WScript.CreateObject("WScript.Shell") > "%TEMP%\CreateShortcuts.vbs"
echo Set oFSO = WScript.CreateObject("Scripting.FileSystemObject") >> "%TEMP%\CreateShortcuts.vbs"
echo strAppPath = "%INSTALL_DIR%" >> "%TEMP%\CreateShortcuts.vbs"
echo strDesktop = oWS.SpecialFolders("Desktop") >> "%TEMP%\CreateShortcuts.vbs"
echo If oFSO.FileExists(strAppPath ^& "\src\ag_mouse_.ico") Then >> "%TEMP%\CreateShortcuts.vbs"
echo     strIcon = strAppPath ^& "\src\ag_mouse_.ico" >> "%TEMP%\CreateShortcuts.vbs"
echo Else >> "%TEMP%\CreateShortcuts.vbs"
echo     strIcon = "%SystemRoot%\System32\SHELL32.dll,3" >> "%TEMP%\CreateShortcuts.vbs"
echo End If >> "%TEMP%\CreateShortcuts.vbs"
echo Set oLink = oWS.CreateShortcut(strDesktop ^& "\DCS GunCam.lnk") >> "%TEMP%\CreateShortcuts.vbs"
echo oLink.TargetPath = strAppPath ^& "\GunCam.bat" >> "%TEMP%\CreateShortcuts.vbs"
echo oLink.WorkingDirectory = strAppPath >> "%TEMP%\CreateShortcuts.vbs"
echo oLink.Description = "DCS GunCam Recording Application" >> "%TEMP%\CreateShortcuts.vbs"
echo oLink.IconLocation = strIcon >> "%TEMP%\CreateShortcuts.vbs"
echo oLink.Save >> "%TEMP%\CreateShortcuts.vbs"

echo [6/9] Creating Start Menu shortcuts...
echo.

REM Add Start Menu shortcuts to the VBScript
echo strStartMenu = oWS.SpecialFolders("Programs") >> "%TEMP%\CreateShortcuts.vbs"
echo If Not oFSO.FolderExists(strStartMenu ^& "\DCS GunCam") Then >> "%TEMP%\CreateShortcuts.vbs"
echo     oFSO.CreateFolder(strStartMenu ^& "\DCS GunCam") >> "%TEMP%\CreateShortcuts.vbs"
echo End If >> "%TEMP%\CreateShortcuts.vbs"
echo Set oLink = oWS.CreateShortcut(strStartMenu ^& "\DCS GunCam\DCS GunCam.lnk") >> "%TEMP%\CreateShortcuts.vbs"
echo oLink.TargetPath = strAppPath ^& "\GunCam.bat" >> "%TEMP%\CreateShortcuts.vbs"
echo oLink.WorkingDirectory = strAppPath >> "%TEMP%\CreateShortcuts.vbs"
echo oLink.Description = "DCS GunCam Recording Application" >> "%TEMP%\CreateShortcuts.vbs"
echo oLink.IconLocation = strIcon >> "%TEMP%\CreateShortcuts.vbs"
echo oLink.Save >> "%TEMP%\CreateShortcuts.vbs"
echo Set oLink = oWS.CreateShortcut(strStartMenu ^& "\DCS GunCam\DCS GunCam Folder.lnk") >> "%TEMP%\CreateShortcuts.vbs"
echo oLink.TargetPath = strAppPath >> "%TEMP%\CreateShortcuts.vbs"
echo oLink.Description = "Open DCS GunCam Installation Folder" >> "%TEMP%\CreateShortcuts.vbs"
echo oLink.IconLocation = strIcon >> "%TEMP%\CreateShortcuts.vbs"
echo oLink.Save >> "%TEMP%\CreateShortcuts.vbs"

cscript //nologo "%TEMP%\CreateShortcuts.vbs"
del "%TEMP%\CreateShortcuts.vbs"

echo [7/9] Configure DCS World autostart...
echo.

REM Check for DCS installation
set "DCS_PATH=%USERPROFILE%\Saved Games"
if exist "%DCS_PATH%\DCS.openbeta\Scripts" (
    set "ACTIVE_DCS_PATH=%DCS_PATH%\DCS.openbeta"
) else if exist "%DCS_PATH%\DCS\Scripts" (
    set "ACTIVE_DCS_PATH=%DCS_PATH%\DCS"
) else (
    echo Warning: Could not find DCS World installation.
    echo Skipping autostart configuration.
    goto SKIP_AUTOSTART
)

:AUTOSTART_PROMPT
echo Found DCS World installation at: %ACTIVE_DCS_PATH%
set /p AUTOSTART="Do you want DCS GunCam to start automatically with DCS World? (Y/N): "
if /i "%AUTOSTART%"=="Y" (
    echo Installing autostart hook...
    if exist "%INSTALL_DIR%\DCS autostart on.bat" (
        cd /d "%INSTALL_DIR%"
        call "DCS autostart on.bat"
    )
) else if /i "%AUTOSTART%"=="N" (
    echo Skipping autostart setup.
) else (
    echo Please enter Y or N.
    goto AUTOSTART_PROMPT
)

:SKIP_AUTOSTART
echo [8/9] Installation Summary
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
if /i "%AUTOSTART%"=="Y" (
    echo DCS World autostart: Enabled
) else (
    echo DCS World autostart: Disabled
)
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