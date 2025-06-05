# service.py - Improved version with proper auto-sync
import win32serviceutil
import win32service
import win32event
import servicemanager
import socket
import sys
import threading
import queue
import time
import os
import logging
import json
from datetime import datetime, timedelta

try:
    from pywin32 import win32timezone
except ImportError:
    # Fallback for systems where pywin32 isn't properly installed
    import win32timezone

import appdirs

APP_NAME = "OfflineMode"
SETTINGS_DIR = appdirs.user_data_dir(APP_NAME)
os.makedirs(SETTINGS_DIR, exist_ok=True)
SETTINGS_FILE = os.path.join(SETTINGS_DIR, "settings.json")

class OfflineModeService(win32serviceutil.ServiceFramework):
    _svc_name_ = "OfflineModeService"
    _svc_display_name_ = "Offline Mode Background Service"
    _svc_description_ = "Automatically syncs Raindrop.io bookmarks every 12 hours"
    
    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
        self.is_running = True
        self.last_sync_time = None
        self.sync_lock = threading.Lock()
        self.sync_thread = None
        
        # Configure logging with better error handling
        try:
            log_dir = os.path.join(os.environ.get('PROGRAMDATA', 'C:\\ProgramData'), 'OfflineMode', 'Logs')
            os.makedirs(log_dir, exist_ok=True)
            log_file = os.path.join(log_dir, 'service.log')
            
            # Configure logging with rotation
            logging.basicConfig(
                filename=log_file,
                level=logging.INFO,
                format='%(asctime)s - %(levelname)s - %(message)s',
                filemode='a'
            )
            self.logger = logging.getLogger()
            
            # Also log to Windows Event Log
            self.logger.addHandler(logging.StreamHandler())
            
        except Exception as e:
            # Fallback logging if directory creation fails
            logging.basicConfig(level=logging.INFO)
            self.logger = logging.getLogger()
            self.logger.error(f"Failed to setup file logging: {e}")

    def SvcStop(self):
        """Service stop handler"""
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        self.logger.info("Service stop requested")
        self.is_running = False
        
        # Signal any running sync to stop
        if self.sync_thread and self.sync_thread.is_alive():
            self.logger.info("Waiting for sync thread to complete...")
            self.sync_thread.join(timeout=10)  # Wait max 10 seconds
        
        win32event.SetEvent(self.hWaitStop)
        self.logger.info("Service stopped gracefully")

    def SvcDoRun(self):
        """Main service entry point"""
        servicemanager.LogMsg(
            servicemanager.EVENTLOG_INFORMATION_TYPE,
            servicemanager.PYS_SERVICE_STARTED,
            (self._svc_name_, '')
        )
        self.logger.info("OfflineMode Service started")
        
        try:
            self.main()
        except Exception as e:
            self.logger.error(f"Service main loop error: {e}")
            raise

    def main(self):
        """Main service loop"""
        try:
            # Load last sync time from file
            self._load_last_sync_time()
            
            # Check if we need to run sync immediately (catch up from shutdown)
            if self._check_missed_syncs():
                self.logger.info("Running catch-up sync due to missed sync periods")
                self._run_sync_async()
            
            # Main service loop
            while self.is_running:
                try:
                    # Check if it's time for next sync
                    if self._is_sync_time():
                        self.logger.info("Regular sync time reached")
                        self._run_sync_async()
                    
                    # Sleep for 1 minute before checking again
                    if self.is_running:
                        time.sleep(60)
                        
                except Exception as e:
                    self.logger.error(f"Error in main loop: {e}")
                    time.sleep(60)  # Continue after error
                    
        except Exception as e:
            self.logger.error(f"Fatal service error: {e}")
            raise

    def _is_sync_time(self):
        """Check if it's time to run a sync"""
        if not self.last_sync_time:
            return True  # Never synced before
            
        now = datetime.now()
        time_since_last_sync = (now - self.last_sync_time).total_seconds()
        hours_since_last_sync = time_since_last_sync / 3600
        
        # Sync every 12 hours
        return hours_since_last_sync >= 12.0

    def _check_missed_syncs(self):
        """Check if any syncs were missed while the service was stopped"""
        if not self.last_sync_time:
            self.logger.info("No previous sync recorded")
            return True  # First time running, do sync
            
        now = datetime.now()
        time_since_last_sync = now - self.last_sync_time
        hours_since_last_sync = time_since_last_sync.total_seconds() / 3600
        
        self.logger.info(f"Hours since last sync: {hours_since_last_sync:.1f}")
        
        # If more than 12 hours since last sync, we missed at least one
        if hours_since_last_sync > 12:
            self.logger.info(f"Detected missed sync period ({hours_since_last_sync:.1f} hours since last sync)")
            return True
            
        return False

    def _run_sync_async(self):
        """Start sync operation in a separate thread"""
        with self.sync_lock:
            if self.sync_thread and self.sync_thread.is_alive():
                self.logger.info("Sync already in progress - skipping")
                return
            
            self.logger.info("Starting sync thread")
            self.sync_thread = threading.Thread(
                target=self._run_sync,
                daemon=True
            )
            self.sync_thread.start()

    def _run_sync(self):
        """Run the actual sync process"""
        try:
            self.logger.info("Sync process started")
            
            # Load settings
            settings = self._load_settings()
            if not settings:
                self.logger.error("Could not load settings - sync aborted")
                return False
            
            # Validate required settings
            if not settings.get('token') or not settings.get('path'):
                self.logger.error("Missing required settings (token or path) - sync aborted")
                return False
            
            # Import and run offline sync
            try:
                import offline
                
                # Verify directory structure
                offline.verify_directory_structure(settings['path'])
                
                # Run sync with settings
                success = offline.sync(
                    settings['token'],
                    settings['path'],
                    settings.get('resolution', '720'),
                    settings.get('delimiter', '#$@'),
                    settings.get('video', False),
                    None  # No stop event for service sync
                )
                
                if success:
                    self.last_sync_time = datetime.now()
                    self._save_last_sync_time()
                    self.logger.info(f"Sync completed successfully at {self.last_sync_time}")
                    return True
                else:
                    self.logger.error("Sync failed")
                    return False
                    
            except ImportError as e:
                self.logger.error(f"Could not import offline module: {e}")
                return False
            except Exception as e:
                self.logger.error(f"Sync execution error: {e}")
                return False
                
        except Exception as e:
            self.logger.error(f"Sync thread error: {e}")
            return False

    def _load_settings(self):
        """Load settings from file"""
        try:
            if os.path.exists(SETTINGS_FILE):
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    settings = json.load(f)
                    self.logger.info("Settings loaded successfully")
                    return settings
            else:
                self.logger.warning(f"Settings file not found: {SETTINGS_FILE}")
                return None
        except Exception as e:
            self.logger.error(f"Error loading settings: {e}")
            return None

    def _load_last_sync_time(self):
        """Load last sync time from file"""
        try:
            sync_dir = os.path.join(os.environ.get('PROGRAMDATA', 'C:\\ProgramData'), 'OfflineMode')
            sync_file = os.path.join(sync_dir, 'last_sync.txt')
            
            if os.path.exists(sync_file):
                with open(sync_file, 'r') as f:
                    timestamp = float(f.read().strip())
                    self.last_sync_time = datetime.fromtimestamp(timestamp)
                    self.logger.info(f"Loaded last sync time: {self.last_sync_time}")
            else:
                self.logger.info("No previous sync time found")
                self.last_sync_time = None
                
        except Exception as e:
            self.logger.warning(f"Could not load last sync time: {e}")
            self.last_sync_time = None

    def _save_last_sync_time(self):
        """Save last sync time to file"""
        try:
            sync_dir = os.path.join(os.environ.get('PROGRAMDATA', 'C:\\ProgramData'), 'OfflineMode')
            os.makedirs(sync_dir, exist_ok=True)
            sync_file = os.path.join(sync_dir, 'last_sync.txt')
            
            with open(sync_file, 'w') as f:
                f.write(str(self.last_sync_time.timestamp()))
                
            self.logger.info(f"Saved last sync time: {self.last_sync_time}")
            
        except Exception as e:
            self.logger.error(f"Could not save last sync time: {e}")

# Service management functions
def install_service():
    """Install the service"""
    try:
        win32serviceutil.InstallService(
            OfflineModeService,
            OfflineModeService._svc_name_,
            OfflineModeService._svc_display_name_,
            description=OfflineModeService._svc_description_
        )
        print(f"Service '{OfflineModeService._svc_display_name_}' installed successfully")
        
        # Set service to start automatically
        import win32service
        hscm = win32service.OpenSCManager(None, None, win32service.SC_MANAGER_ALL_ACCESS)
        try:
            hs = win32service.OpenService(hscm, OfflineModeService._svc_name_, win32service.SERVICE_ALL_ACCESS)
            try:
                win32service.ChangeServiceConfig(
                    hs,
                    win32service.SERVICE_NO_CHANGE,
                    win32service.SERVICE_AUTO_START,  # Start automatically
                    win32service.SERVICE_NO_CHANGE,
                    None, None, 0, None, None, None, None
                )
                print("Service set to start automatically")
            finally:
                win32service.CloseServiceHandle(hs)
        finally:
            win32service.CloseServiceHandle(hscm)
            
    except Exception as e:
        print(f"Failed to install service: {e}")

def start_service():
    """Start the service"""
    try:
        win32serviceutil.StartService(OfflineModeService._svc_name_)
        print(f"Service '{OfflineModeService._svc_display_name_}' started successfully")
    except Exception as e:
        print(f"Failed to start service: {e}")

def stop_service():
    """Stop the service"""
    try:
        win32serviceutil.StopService(OfflineModeService._svc_name_)
        print(f"Service '{OfflineModeService._svc_display_name_}' stopped successfully")
    except Exception as e:
        print(f"Failed to stop service: {e}")

def remove_service():
    """Remove the service"""
    try:
        # Stop service first if running
        try:
            stop_service()
            time.sleep(2)  # Give it time to stop
        except:
            pass  # Ignore if already stopped
            
        win32serviceutil.RemoveService(OfflineModeService._svc_name_)
        print(f"Service '{OfflineModeService._svc_display_name_}' removed successfully")
    except Exception as e:
        print(f"Failed to remove service: {e}")

if __name__ == '__main__':
    if len(sys.argv) == 1:
        # Run as service
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(OfflineModeService)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        # Handle command line arguments
        if 'install' in sys.argv:
            install_service()
        elif 'start' in sys.argv:
            start_service()
        elif 'stop' in sys.argv:
            stop_service()
        elif 'remove' in sys.argv or 'uninstall' in sys.argv:
            remove_service()
        else:
            # Use standard service utilities
            win32serviceutil.HandleCommandLine(OfflineModeService)