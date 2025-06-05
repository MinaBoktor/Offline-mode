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

echo ================================
echo  OfflineMode Service Management
echo ================================
echo.

:: Check if service executable exists
if not exist "%SCRIPT_DIR%%SERVICE_EXE%" (
    echo ERROR: Service executable not found: %SCRIPT_DIR%%SERVICE_EXE%
    echo Please make sure the service executable is in the same directory as this script.
    pause
    exit /b 1
)

:MENU
echo Please select an option:
echo 1) Install and Start Service
echo 2) Stop Service
echo 3) Start Service
echo 4) Remove Service
echo 5) Check Service Status
echo 6) View Service Logs
echo 7) Exit
echo.
set /p choice="Enter your choice (1-7): "

if "%choice%"=="1" goto INSTALL
if "%choice%"=="2" goto STOP
if "%choice%"=="3" goto START
if "%choice%"=="4" goto REMOVE
if "%choice%"=="5" goto STATUS
if "%choice%"=="6" goto LOGS
if "%choice%"=="7" goto EXIT

echo Invalid choice. Please try again.
echo.
goto MENU

:INSTALL
echo Installing OfflineMode Service...
"%SCRIPT_DIR%%SERVICE_EXE%" install
if %errorLevel% neq 0 (
    echo ERROR: Failed to install service
    pause
    goto MENU
)

echo Starting OfflineMode Service...
"%SCRIPT_DIR%%SERVICE_EXE%" start
if %errorLevel% neq 0 (
    echo ERROR: Failed to start service
    pause
    goto MENU
)

echo.
echo Service installed and started successfully!
echo The service will now automatically sync your bookmarks every 12 hours.
echo.
goto MENU

:STOP
echo Stopping OfflineMode Service...
"%SCRIPT_DIR%%SERVICE_EXE%" stop
if %errorLevel% neq 0 (
    echo ERROR: Failed to stop service
    pause
    goto MENU
)
echo Service stopped successfully!
echo.
goto MENU

:START
echo Starting OfflineMode Service...
"%SCRIPT_DIR%%SERVICE_EXE%" start
if %errorLevel% neq 0 (
    echo ERROR: Failed to start service
    pause
    goto MENU
)
echo Service started successfully!
echo.
goto MENU

:REMOVE
echo Stopping OfflineMode Service (if running)...
"%SCRIPT_DIR%%SERVICE_EXE%" stop >nul 2>&1

echo Removing OfflineMode Service...
"%SCRIPT_DIR%%SERVICE_EXE%" remove
if %errorLevel% neq 0 (
    echo ERROR: Failed to remove service
    pause
    goto MENU
)
echo Service removed successfully!
echo.
goto MENU

:STATUS
echo Checking service status...
sc query %SERVICE_NAME% >nul 2>&1
if %errorLevel% neq 0 (
    echo Service is NOT INSTALLED
) else (
    sc query %SERVICE_NAME%
)
echo.
goto MENU

:LOGS
echo Opening service logs directory...
set LOG_DIR=%PROGRAMDATA%\OfflineMode\Logs
if exist "%LOG_DIR%" (
    explorer "%LOG_DIR%"
    echo Log directory opened in Windows Explorer.
    echo Look for 'service.log' file for detailed service logs.
) else (
    echo Log directory not found: %LOG_DIR%
    echo The service may not have been started yet.
)
echo.
goto MENU

:EXIT
echo Goodbye!
exit /b 0