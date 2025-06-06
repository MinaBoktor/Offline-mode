@echo off
setlocal enabledelayedexpansion

:: === Configuration ===
set PYTHON=python
set APP_NAME=OfflineMode
set INSTALLER_PATH="%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"

:: Get absolute path to the script directory
for %%I in ("%CD%") do set SCRIPT_DIR=%%~fI

echo ========================================
echo  Building %APP_NAME% with Auto-Service
echo ========================================

:: Check required files
if not exist "%SCRIPT_DIR%\requirements.txt" (
    echo ERROR: requirements.txt not found in %SCRIPT_DIR%
    exit /b 1
)

if not exist "%SCRIPT_DIR%\offline.ico" (
    echo ERROR: offline.ico not found in %SCRIPT_DIR%
    exit /b 1
)

if not exist "%SCRIPT_DIR%\service.py" (
    echo ERROR: service.py not found in %SCRIPT_DIR%
    exit /b 1
)

if not exist "%SCRIPT_DIR%\offline.py" (
    echo ERROR: offline.py not found in %SCRIPT_DIR%
    exit /b 1
)

:: Clean previous build artifacts
echo Cleaning previous builds...
if exist "%SCRIPT_DIR%\build" rmdir /s /q "%SCRIPT_DIR%\build"
if exist "%SCRIPT_DIR%\dist" rmdir /s /q "%SCRIPT_DIR%\dist"

:: Create build directory structure
mkdir "%SCRIPT_DIR%\dist"
mkdir "%SCRIPT_DIR%\dist\setup_package"
mkdir "%SCRIPT_DIR%\build"

:: === Generate hidden imports from requirements.txt ===
set HIDDEN_IMPORTS=
for /f "usebackq tokens=1 delims=><= #" %%i in (`type "%SCRIPT_DIR%\requirements.txt"`) do (
    set "module=%%i"
    set "module=!module: =!"  :: Remove spaces
    if not "!module!"=="" (
        set HIDDEN_IMPORTS=!HIDDEN_IMPORTS! --hidden-import=!module!
    )
)

:: Additional required hidden imports for service
set EXTRA_IMPORTS=--hidden-import=pystray._win32 --hidden-import=pystray._darwin --hidden-import=pystray._x11
set EXTRA_IMPORTS=!EXTRA_IMPORTS! --hidden-import=concurrent.futures --hidden-import=threading --hidden-import=queue
set EXTRA_IMPORTS=!EXTRA_IMPORTS! --hidden-import=concurrent_log_handler --hidden-import=monolith
set EXTRA_IMPORTS=!EXTRA_IMPORTS! --hidden-import=pywin32 --hidden-import=win32serviceutil
set EXTRA_IMPORTS=!EXTRA_IMPORTS! --hidden-import=win32service --hidden-import=win32event --hidden-import=servicemanager
set EXTRA_IMPORTS=!EXTRA_IMPORTS! --hidden-import=win32timezone --hidden-import=win32api --hidden-import=win32con
set EXTRA_IMPORTS=!EXTRA_IMPORTS! --hidden-import=pywintypes --hidden-import=logging.handlers
set EXTRA_IMPORTS=!EXTRA_IMPORTS! --hidden-import=appdirs --hidden-import=json --hidden-import=datetime

:: === Build main application ===
echo.
echo [1/3] Building main application...
%PYTHON% -m PyInstaller ^
    --onefile ^
    --noconsole ^
    --icon "%SCRIPT_DIR%\offline.ico" ^
    --name "%APP_NAME%" ^
    --add-data "%SCRIPT_DIR%\offline.ico;." ^
    --add-data "%SCRIPT_DIR%\offline.py;." ^
    --distpath "%SCRIPT_DIR%\dist\setup_package" ^
    --workpath "%SCRIPT_DIR%\build" ^
    --noconfirm ^
    %HIDDEN_IMPORTS% %EXTRA_IMPORTS% ^
    "%SCRIPT_DIR%\settings_app.py"

if errorlevel 1 (
    echo ERROR: Failed building main application
    exit /b 1
)
echo ✓ Main application built successfully

:: === Build service executable ===
echo.
echo [2/3] Building service executable...
%PYTHON% -m PyInstaller ^
    --onefile ^
    --console ^
    --icon "%SCRIPT_DIR%\offline.ico" ^
    --add-data "%SCRIPT_DIR%\offline.ico;." ^
    --add-data "%SCRIPT_DIR%\offline.py;." ^
    --add-data "%SCRIPT_DIR%\web.py;." ^
    --add-data "%SCRIPT_DIR%\youtube.py;." ^
    --name "%APP_NAME%_service" ^
    --distpath "%SCRIPT_DIR%\dist\setup_package" ^
    --workpath "%SCRIPT_DIR%\build" ^
    --noconfirm ^
    --hidden-import win32timezone ^
    --hidden-import win32service ^
    --hidden-import win32event ^
    --hidden-import servicemanager ^
    --hidden-import concurrent_log_handler ^
    --hidden-import pystray._win32 ^
    --hidden-import pywintypes ^
    "%SCRIPT_DIR%\service.py"

if errorlevel 1 (
    echo ERROR: Failed building service executable
    exit /b 1
)
echo ✓ Service executable built successfully

:: === Copy required files to setup package ===
echo.
echo [3/3] Preparing installation package...
copy "%SCRIPT_DIR%\offline.ico" "%SCRIPT_DIR%\dist\setup_package\" >nul
copy "%SCRIPT_DIR%\requirements.txt" "%SCRIPT_DIR%\dist\setup_package\" >nul
copy "%SCRIPT_DIR%\service.bat" "%SCRIPT_DIR%\dist\setup_package\" >nul
copy "%SCRIPT_DIR%\setup.py" "%SCRIPT_DIR%\dist\setup_package\" >nul
copy "%SCRIPT_DIR%\offline.py" "%SCRIPT_DIR%\dist\setup_package\" >nul
copy "%SCRIPT_DIR%\web.py" "%SCRIPT_DIR%\dist\setup_package\" >nul
copy "%SCRIPT_DIR%\youtube.py" "%SCRIPT_DIR%\dist\setup_package\" >nul

:: Create installation script
echo Creating installation script...
(
echo @echo off
echo echo ========================================
echo echo  Installing %APP_NAME% with Auto-Service
echo echo ========================================
echo echo.
echo echo Installing application and dependencies...
echo python -m pip install --upgrade pip
echo cd /d %%~dp0
echo python setup.py install
echo echo.
echo echo Installation completed!
echo echo The background sync service has been installed and started automatically.
echo echo It will sync your bookmarks every 5 minutes.
echo echo.
echo echo You can now run '%APP_NAME%' from your desktop shortcut or Start Menu.
echo echo.
echo pause
) > "%SCRIPT_DIR%\dist\setup_package\install.bat"

:: Create enhanced service management script
(
echo @echo off
echo setlocal enabledelayedexpansion
echo.
echo :: Check if running as administrator
echo net session ^>nul 2^>^&1
echo if %%errorLevel%% neq 0 ^(
echo     echo ==========================================
echo     echo  ADMINISTRATOR PRIVILEGES REQUIRED
echo     echo ==========================================
echo     echo This script must be run as Administrator to install/manage Windows services.
echo     echo.
echo     echo Please:
echo     echo 1. Right-click on this batch file
echo     echo 2. Select "Run as administrator"
echo     echo 3. Click "Yes" when prompted by UAC
echo     echo.
echo     pause
echo     exit /b 1
echo ^)
echo.
echo set SERVICE_NAME=OfflineModeService
echo set SERVICE_EXE=%APP_NAME%_service.exe
echo set SCRIPT_DIR=%%~dp0
echo.
echo echo

:: Create service debug script
(
echo @echo off
echo echo ========================================
echo echo  Running %APP_NAME% Service in Debug Mode
echo echo ========================================
echo echo This will run the service in console mode for debugging.
echo echo Press Ctrl+C to stop the service.
echo echo.
echo pause
echo.
echo "%~dp0%APP_NAME%_service.exe" debug
echo.
echo pause
) > "%SCRIPT_DIR%\dist\setup_package\debug_service.bat"

:: Create readme file
(
echo %APP_NAME% Installation Package
echo ================================
echo.
echo This package includes:
echo - %APP_NAME%.exe ^(Main application^)
echo - %APP_NAME%_service.exe ^(Background sync service^)
echo - install.bat ^(Run this to install^)
echo - manage_service.bat ^(Service management tool^)
echo - debug_service.bat ^(Debug the service^)
echo.
echo Installation:
echo 1. Right-click on 'install.bat' and select "Run as administrator"
echo 2. Wait for installation to complete
echo 3. The service will be installed and started automatically
echo 4. Use the desktop shortcut or Start Menu to run the application
echo.
echo Service Management:
echo - Use 'manage_service.bat' to start/stop/reinstall the service
echo - The service syncs your bookmarks every 5 minutes automatically
echo - Use 'debug_service.bat' to run the service in console mode for debugging
echo - Check Windows Services ^(services.msc^) for "Offline Mode Background Service"
echo.
echo Troubleshooting:
echo - If sync isn't working, check the service logs in %%PROGRAMDATA%%\OfflineMode\Logs\
echo - Run 'debug_service.bat' to see what's happening in real-time
echo - Make sure to configure your settings in the main application first
echo.
echo Uninstallation:
echo 1. Use 'manage_service.bat' to remove the service first
echo 2. Uninstall through Windows "Add or Remove Programs"
) > "%SCRIPT_DIR%\dist\setup_package\README.txt"

:: === Create installer if Inno Setup is available ===
if exist %INSTALLER_PATH% (
    echo.
    echo Creating installer...
    %INSTALLER_PATH% /Q "%SCRIPT_DIR%\installer.iss"
    if errorlevel 1 (
        echo WARNING: Failed creating installer
    ) else (
        echo ✓ Installer created successfully
    )
) else (
    echo.
    echo WARNING: Inno Setup not found at %INSTALLER_PATH%
    echo Installer creation skipped - using manual installation package
)

:: === Create distribution ZIP ===
echo.
echo Creating distribution archive...
powershell -Command "Compress-Archive -Path '%SCRIPT_DIR%\dist\setup_package\*' -DestinationPath '%SCRIPT_DIR%\dist\%APP_NAME%_Setup.zip' -Force"

:: === Build complete ===
echo.
echo ========================================
echo  BUILD COMPLETED SUCCESSFULLY!
echo ========================================
echo.
echo Package contents:
echo   Main executable:       %APP_NAME%.exe
echo   Service executable:    %APP_NAME%_service.exe
echo   Installation script:   install.bat
echo   Service manager:       manage_service.bat
echo   Service debugger:      debug_service.bat
echo   Documentation:         README.txt
echo.
echo Package location:
echo   Directory: %SCRIPT_DIR%\dist\setup_package\
echo   Archive:   %SCRIPT_DIR%\dist\%APP_NAME%_Setup.zip

if exist %INSTALLER_PATH% (
    echo   Installer: %SCRIPT_DIR%\dist\Output\setup.exe
)

echo.
echo INSTALLATION INSTRUCTIONS:
echo 1. Navigate to: %SCRIPT_DIR%\dist\setup_package\
echo 2. Right-click 'install.bat' and select "Run as administrator"
echo 3. The service will be installed and started automatically
echo 4. Service will sync every 5 minutes automatically
echo.
echo DEBUGGING:
echo - Run 'debug_service.bat' to test the service in console mode
echo - Check logs in %%PROGRAMDATA%%\OfflineMode\Logs\service.log
echo.
pause