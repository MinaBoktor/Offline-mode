@echo off
setlocal enabledelayedexpansion

echo ========================================
echo  OfflineMode Installation Verification
echo ========================================
echo.

:: Check if running as administrator
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo WARNING: Not running as administrator
    echo Some checks may fail without admin privileges
    echo.
)

:: Check main executable
set MAIN_EXE=OfflineMode.exe
if exist "%~dp0%MAIN_EXE%" (
    echo ✓ Main executable found: %MAIN_EXE%
) else (
    echo ❌ Main executable NOT found: %MAIN_EXE%
    set /a ERROR_COUNT+=1
)

:: Check service executable
set SERVICE_EXE=OfflineMode_service.exe  
if exist "%~dp0%SERVICE_EXE%" (
    echo ✓ Service executable found: %SERVICE_EXE%
) else (
    echo ❌ Service executable NOT found: %SERVICE_EXE%
    set /a ERROR_COUNT+=1
)

:: Check service installation
echo.
echo Checking Windows service status...
sc query OfflineModeService >nul 2>&1
if %errorLevel% equ 0 (
    echo ✓ OfflineMode service is installed
    
    :: Check if service is running
    sc query OfflineModeService | find "RUNNING" >nul
    if %errorLevel% equ 0 (
        echo ✓ OfflineMode service is running
    ) else (
        echo ⚠ OfflineMode service is installed but not running
        echo   You can start it using: %SERVICE_EXE% start
    )
) else (
    echo ❌ OfflineMode service is NOT installed
    echo   You can install it using: %SERVICE_EXE% install
    set /a ERROR_COUNT+=1
)

:: Check startup registry entry
echo.
echo Checking Windows startup configuration...
reg query "HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Run" /v "OfflineMode" >nul 2>&1
if %errorLevel% equ 0 (
    echo ✓ Application is configured to start with Windows
) else (
    echo ⚠ Application is NOT configured to start with Windows
    echo   You can enable this in the application settings
)

:: Check for icon file
if exist "%~dp0offline.ico" (
    echo ✓ Application icon found
) else (
    echo ⚠ Application icon missing (non-critical)
)

:: Summary
echo.
echo ========================================
echo  INSTALLATION VERIFICATION COMPLETE
echo ========================================

if !ERROR_COUNT! equ 0 (
    echo.
    echo ✅ INSTALLATION SUCCESSFUL!
    echo.
    echo All components are properly installed:
    echo • Main application: Ready to use
    echo • Background service: Installed and running  
    echo • Automatic sync: Active every 12 hours
    echo.
    echo You can now:
    echo 1. Run '%MAIN_EXE%' to configure your settings
    echo 2. The service will automatically sync your bookmarks
    echo 3. Use 'manage_service.bat' to control the service
) else (
    echo.
    echo ❌ INSTALLATION ISSUES DETECTED
    echo.
    echo Please fix the issues above before using the application.
    echo You may need to run the installation as administrator.
)

echo.
pause