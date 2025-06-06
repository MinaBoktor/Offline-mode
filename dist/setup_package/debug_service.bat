@echo off
setlocal enabledelayedexpansion

:: Check if running as administrator
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo ==========================================
    echo  ADMINISTRATOR PRIVILEGES REQUIRED
    echo ==========================================
    echo This script must be run as Administrator to install/manage Windows services.
    echo.
    echo Please:
    echo 1. Right-click on this batch file
    echo 2. Select "Run as administrator"
    echo 3. Click "Yes" when prompted by UAC
    echo.
    pause
    exit /b 1
)

set SERVICE_NAME=OfflineModeService
set SERVICE_EXE=OfflineMode_service.exe
set SCRIPT_DIR=%~dp0

echo
@echo off
echo ========================================
echo  Running OfflineMode Service in Debug Mode
echo ========================================
echo This will run the service in console mode for debugging.
echo Press Ctrl+C to stop the service.
echo.
pause

"C:\Users\RexoL\source\repos\Offline-mode\OfflineMode_service.exe" debug

pause
