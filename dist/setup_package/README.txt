OfflineMode Installation Package
================================

This package includes:
- OfflineMode.exe (Main application)
- OfflineMode_service.exe (Background sync service)
- install.bat (Run this to install)
- manage_service.bat (Service management tool)

Installation:
1. Right-click on 'install.bat' and select "Run as administrator"
2. Wait for installation to complete
3. The service will be installed and started automatically
4. Use the desktop shortcut or Start Menu to run the application

Service Management:
- Use 'manage_service.bat' to start/stop/reinstall the service
- The service syncs your bookmarks every 12 hours automatically
- Check Windows Services (services.msc) for "Offline Mode Background Service"

Uninstallation:
1. Use 'manage_service.bat' to remove the service first
2. Uninstall through Windows "Add or Remove Programs"
