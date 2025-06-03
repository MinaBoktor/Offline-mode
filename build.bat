@echo off
setlocal enabledelayedexpansion

:: === Configuration ===
set PYTHON=python
set APP_NAME=OfflineMode
set INSTALLER_PATH="%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"

:: Get absolute path to the script directory
for %%I in ("%CD%") do set SCRIPT_DIR=%%~fI

:: Check required files
if not exist "%SCRIPT_DIR%\requirements.txt" (
    echo ERROR: requirements.txt not found in %SCRIPT_DIR%
    exit /b 1
)

if not exist "%SCRIPT_DIR%\offline.ico" (
    echo ERROR: offline.ico not found in %SCRIPT_DIR%
    exit /b 1
)

:: Clean previous build artifacts (optional but recommended)
if exist "%SCRIPT_DIR%\build" rmdir /s /q "%SCRIPT_DIR%\build"
if exist "%SCRIPT_DIR%\dist" rmdir /s /q "%SCRIPT_DIR%\dist"

:: Create build directory structure
mkdir "%SCRIPT_DIR%\dist"
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

:: Additional required hidden imports (manually specified)
set EXTRA_IMPORTS=--hidden-import=pystray._win32 --hidden-import=pystray._darwin --hidden-import=pystray._x11
set EXTRA_IMPORTS=!EXTRA_IMPORTS! --hidden-import=concurrent.futures --hidden-import=threading --hidden-import=queue
set EXTRA_IMPORTS=!EXTRA_IMPORTS! --hidden-import=concurrent_log_handler --hidden-import=monolith
set EXTRA_IMPORTS=!EXTRA_IMPORTS! --hidden-import=pywin32

:: === Build main application ===
echo Building main application...
%PYTHON% -m PyInstaller ^
    --onefile ^
    --noconsole ^
    --icon "%SCRIPT_DIR%\offline.ico" ^
    --name "%APP_NAME%" ^
    --add-data "%SCRIPT_DIR%\offline.ico;." ^
    --distpath "%SCRIPT_DIR%\dist" ^
    --workpath "%SCRIPT_DIR%\build" ^
    --noconfirm ^
    %HIDDEN_IMPORTS% %EXTRA_IMPORTS% ^
    "%SCRIPT_DIR%\settings_app.py"

if errorlevel 1 (
    echo ERROR: Failed building main application
    exit /b 1
)

:: === Build service executable ===
echo Building service executable...
%PYTHON% -m PyInstaller ^
    --onefile ^
    --noconsole ^
    --icon "%SCRIPT_DIR%\offline.ico" ^
    --add-data "%SCRIPT_DIR%\offline.ico;." ^
    --name "%APP_NAME%_service" ^
    --distpath "%SCRIPT_DIR%\dist" ^
    --workpath "%SCRIPT_DIR%\build" ^
    --noconfirm ^
    %HIDDEN_IMPORTS% %EXTRA_IMPORTS% ^
    "%SCRIPT_DIR%\service.py"

if errorlevel 1 (
    echo ERROR: Failed building service executable
    exit /b 1
)

:: === Create installer if Inno Setup is available ===
if exist %INSTALLER_PATH% (
    echo Creating installer...
    %INSTALLER_PATH% /Q "%SCRIPT_DIR%\installer.iss"
    if errorlevel 1 (
        echo ERROR: Failed creating installer
        exit /b 1
    )
) else (
    echo WARNING: Inno Setup not found at %INSTALLER_PATH%
    echo Installer creation skipped
)

:: === Copy required files to dist directory ===
copy "%SCRIPT_DIR%\offline.ico" "%SCRIPT_DIR%\dist\" >nul
copy "%SCRIPT_DIR%\requirements.txt" "%SCRIPT_DIR%\dist\" >nul

:: === Build complete ===
echo.
echo Build completed successfully!
echo Main executable:       %SCRIPT_DIR%\dist\%APP_NAME%.exe
echo Service executable:    %SCRIPT_DIR%\dist\%APP_NAME%_service.exe

if exist %INSTALLER_PATH% (
    echo Installer:           %SCRIPT_DIR%\dist\Output\setup.exe
)

pause
