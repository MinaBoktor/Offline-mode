@echo off
echo ========================================
echo  Installing OfflineMode with Auto-Service
echo ========================================
echo.
echo Installing application and dependencies...
python -m pip install --upgrade pip
cd /d %~dp0
python setup.py install
echo.
echo Installation completed
echo The background sync service has been installed and started automatically.
echo It will sync your bookmarks every 5 minutes.
echo.
echo You can now run 'OfflineMode' from your desktop shortcut or Start Menu.
echo.
pause
