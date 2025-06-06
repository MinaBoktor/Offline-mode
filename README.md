# Offline Mode - Raindrop.io Bookmark Sync Tool

![Offline Mode Logo](offline.ico)

Offline Mode is a Windows application that automatically syncs your Raindrop.io bookmarks to local storage, including articles and videos, with a background service for regular updates.

## Features

- **Automatic Sync**: Background service syncs bookmarks every 12 hours
- **Offline Access**: Save web articles and videos for offline viewing
- **Video Downloads**: Optional video downloading at specified resolutions
- **System Tray Integration**: Runs minimized with system tray controls
- **Windows Service**: Reliable background operation
- **Archive Functionality**: Automatically archives removed bookmarks

## System Requirements

- Windows 10 or later
- Python 3.8+ (included in installer)
- Raindrop.io API token
- Internet connection for syncing

## Installation

### Automated Installer
1. Download the latest installer (`OfflineMode_Setup.exe`)
2. Right-click and select "Run as administrator"
3. Follow the installation wizard
4. The service will be installed and started automatically

### Manual Installation
1. Extract the ZIP package
2. Right-click `install.bat` and select "Run as administrator"
3. The application and service will be installed

## Configuration

After installation:
1. Launch Offline Mode from the Start Menu or desktop shortcut
2. Enter your Raindrop.io API token
3. Set your download path
4. Configure video download settings (if needed)
5. Click "Save Settings"

### Obtaining API Token
1. Log in to [Raindrop.io](https://app.raindrop.io)
2. Go to Settings → Developer
3. Create a new app and copy the API token

## Usage

### Main Application
- **Run Sync**: Manually trigger a sync operation
- **Settings**: Configure your sync preferences
- **Start with Windows**: Option to launch on startup

### Service Management
Use `manage_service.bat` for advanced control:
- Start/Stop service
- Check service status
- View service logs
- Remove service

### Command Line Options
- `--silent`: Run in background mode
- `--hidden`: Start minimized

### Service Behavior
- Syncs every 12 hours by default
- Logs to `%PROGRAMDATA%\OfflineMode\Logs\service.log`
- Runs as Windows Service (`OfflineModeService`)

## Troubleshooting

### Common Issues

**Service not running:**
1. Open `manage_service.bat` as admin
2. Select "Start Service"
3. Check logs if issues persist

**Sync failures:**
1. Verify API token is correct
2. Check internet connection
3. Verify sufficient disk space

**Debugging:**
- Use `debug_service.bat` to run in console mode
- Check Windows Event Viewer for service errors

## Uninstallation

1. Use `manage_service.bat` to stop and remove the service
2. Uninstall via Windows "Add or Remove Programs"
3. Delete any remaining files in installation directory

## Development

### Build Instructions

1. Install requirements:
   ```bash
   pip install -r requirements.txt