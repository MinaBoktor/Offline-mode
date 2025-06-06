import win32serviceutil
import win32service
import win32event
import servicemanager
import socket
import sys
import threading
import time
import os
import logging
import logging.handlers
import json
import traceback
from datetime import datetime
import getpass

import appdirs

APP_NAME = "OfflineMode"



# Directories and files
BASE_DIR = os.path.join(os.environ.get('Program Files (x86)', r'C:\Program Files (x86)'), APP_NAME)
LOG_DIR = os.path.join(BASE_DIR, 'Logs')
SETTINGS_DIR = fr"C:\Users\RexoL\AppData\Local\OfflineMode\OfflineMode"
SETTINGS_FILE = os.path.join(SETTINGS_DIR, "settings.json")
LAST_SYNC_FILE = os.path.join(BASE_DIR, 'last_sync.txt')


SYNC_INTERVAL_MINUTES = 720  # 5 minutes for testing
CHECK_INTERVAL_SECONDS = 1800  # Check every 30 seconds instead of 60

class OfflineModeService(win32serviceutil.ServiceFramework):
    _svc_name_ = "OfflineModeService"
    _svc_display_name_ = "Offline Mode Background Service"
    _svc_description_ = "Automatically syncs Raindrop.io bookmarks every 5 minutes"

    def __init__(self, args):
        super().__init__(args)
        self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
        self.is_running = True
        self.last_sync_time = None
        self.sync_lock = threading.Lock()
        self.sync_thread = None
        self.stop_event = threading.Event()

        # Setup logging first
        self._setup_logging()
        self.logger.info("Service initialized")

    def _setup_logging(self):
        """Setup comprehensive logging"""
        try:
            # Ensure log directory exists
            os.makedirs(LOG_DIR, exist_ok=True)
            log_file = os.path.join(LOG_DIR, 'service.log')

            self.logger = logging.getLogger('OfflineModeService')
            self.logger.setLevel(logging.DEBUG)  # More verbose logging

            # Clear any existing handlers
            while self.logger.handlers:
                self.logger.handlers.pop()

            # Console handler for debugging
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.INFO)
            console_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            console_handler.setFormatter(console_formatter)
            self.logger.addHandler(console_handler)

            # File handler with rotation
            file_handler = logging.handlers.RotatingFileHandler(
                log_file, maxBytes=10*1024*1024, backupCount=5, encoding='utf-8'
            )
            file_handler.setLevel(logging.DEBUG)
            file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            file_handler.setFormatter(file_formatter)
            self.logger.addHandler(file_handler)

            # Windows Event Log handler (optional)
            try:
                event_handler = logging.handlers.NTEventLogHandler(APP_NAME)
                event_handler.setLevel(logging.WARNING)  # Only warnings and errors
                event_formatter = logging.Formatter('%(levelname)s - %(message)s')
                event_handler.setFormatter(event_formatter)
                self.logger.addHandler(event_handler)
            except Exception as e:
                print(f"Could not add Windows Event Log handler: {e}")

        except Exception as e:
            print(f"Failed to setup logging: {e}")
            # Fallback to basic logging
            logging.basicConfig(level=logging.INFO)
            self.logger = logging.getLogger('OfflineModeService')

    def SvcStop(self):
        """Called when service is asked to stop"""
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        self.logger.info("Service stop requested")

        self.is_running = False
        self.stop_event.set()

        # Wait for sync thread to finish gracefully
        if self.sync_thread and self.sync_thread.is_alive():
            self.logger.info("Waiting for sync thread to stop...")
            self.sync_thread.join(timeout=15)  # Increased timeout
            if self.sync_thread.is_alive():
                self.logger.warning("Sync thread did not stop gracefully")

        win32event.SetEvent(self.hWaitStop)
        self.logger.info("Service stopped")

    def SvcDoRun(self):
        """Main service entry point"""
        try:
            servicemanager.LogMsg(
                servicemanager.EVENTLOG_INFORMATION_TYPE,
                servicemanager.PYS_SERVICE_STARTED,
                (self._svc_name_, '')
            )
            self.logger.info("OfflineMode Service starting...")
            
            # Log configuration
            self.logger.info(f"Sync interval: {SYNC_INTERVAL_MINUTES} minutes")
            self.logger.info(f"Check interval: {CHECK_INTERVAL_SECONDS} seconds")
            self.logger.info(f"Settings file: {SETTINGS_FILE}")
            self.logger.info(f"Log directory: {LOG_DIR}")
            
            self.main()
            
        except Exception as e:
            self.logger.error(f"Fatal error in service: {e}\n{traceback.format_exc()}")
            raise
        finally:
            servicemanager.LogInfoMsg("Offline Mode Background Service stopped.")

    def main(self):
        """Main service loop"""
        try:
            # Load last sync time
            self._load_last_sync_time()

            # Check if we should run an initial sync
            if self._should_run_initial_sync():
                self.logger.info("Running initial sync")
                self._run_sync_async()

            # Main loop
            while self.is_running:
                try:
                    if self._is_sync_time():
                        self.logger.info("Sync interval reached, starting sync")
                        self._run_sync_async()
                    
                    # Wait with periodic checks for stop signal
                    for _ in range(CHECK_INTERVAL_SECONDS):
                        if not self.is_running or self.stop_event.is_set():
                            break
                        time.sleep(1)

                except Exception as e:
                    self.logger.error(f"Error in main loop: {e}\n{traceback.format_exc()}")
                    time.sleep(CHECK_INTERVAL_SECONDS)

        except Exception as e:
            self.logger.error(f"Fatal error in main loop: {e}\n{traceback.format_exc()}")
            raise

    def _should_run_initial_sync(self):
        """Check if we should run an initial sync on startup"""
        if not self.last_sync_time:
            self.logger.info("No previous sync time recorded")
            return True

        now = datetime.now()
        elapsed_minutes = (now - self.last_sync_time).total_seconds() / 60
        self.logger.info(f"Minutes since last sync: {elapsed_minutes:.2f}")

        # Run if it's been longer than our sync interval
        if elapsed_minutes >= SYNC_INTERVAL_MINUTES:
            self.logger.info("Sync interval exceeded, will run initial sync")
            return True

        return False

    def _is_sync_time(self):
        """Check if it's time to sync"""
        if not self.last_sync_time:
            return True

        now = datetime.now()
        elapsed_minutes = (now - self.last_sync_time).total_seconds() / 60
        
        is_time = elapsed_minutes >= SYNC_INTERVAL_MINUTES
        if is_time:
            self.logger.debug(f"Sync time reached: {elapsed_minutes:.2f} minutes elapsed")
        
        return is_time

    def _run_sync_async(self):
        """Start sync in a separate thread"""
        with self.sync_lock:
            if self.sync_thread and self.sync_thread.is_alive():
                self.logger.info("Sync already running, skipping new request")
                return False

            self.logger.info("Starting new sync thread")
            self.sync_thread = threading.Thread(
                target=self._run_sync, 
                name="SyncThread",
                daemon=False  # Don't use daemon threads for critical operations
            )
            self.sync_thread.start()
            return True

    def _run_sync(self):
        """Execute the actual sync operation"""
        sync_start_time = datetime.now()
        
        try:
            self.logger.info(f"Sync process started at {sync_start_time}")
            
            # Load settings
            settings = self._load_settings()
            if not settings:
                self.logger.error("Settings missing or invalid - aborting sync")
                return False

            # Validate required settings
            token = settings.get('token')
            path = settings.get('path')
            
            if not token:
                self.logger.error("Missing 'token' in settings - aborting sync")
                return False
                
            if not path:
                self.logger.error("Missing 'path' in settings - aborting sync")
                return False

            self.logger.info(f"Syncing to path: {path}")
            self.logger.info(f"Using token: {token[:10]}..." if len(token) > 10 else "Using token")

            # Import and run sync
            try:
                # Add current directory to Python path if needed
                current_dir = os.path.dirname(os.path.abspath(__file__))
                if current_dir not in sys.path:
                    sys.path.insert(0, current_dir)
                
                import offline
                
                # Verify directory structure
                path = offline.verify_directory_structure(path)
                self.logger.info(f"Directory structure verified: {path}")

                # Run the sync with our stop event
                success = offline.sync(
                    token=token,
                    path=path,
                    resolution=settings.get('resolution', '720'),
                    delimiter=settings.get('delimiter', '#$@'),
                    VIDEO=settings.get('video', False),
                    stop_event=self.stop_event
                )

                sync_end_time = datetime.now()
                sync_duration = (sync_end_time - sync_start_time).total_seconds()

                if success:
                    self.last_sync_time = sync_end_time
                    self._save_last_sync_time()
                    self.logger.info(f"Sync completed successfully in {sync_duration:.2f} seconds")
                    return True
                else:
                    self.logger.error(f"Sync failed after {sync_duration:.2f} seconds")
                    return False

            except ImportError as e:
                self.logger.error(f"Failed to import 'offline' module: {e}")
                self.logger.error(f"Current working directory: {os.getcwd()}")
                self.logger.error(f"Python path: {sys.path}")
                return False
                
            except Exception as e:
                self.logger.error(f"Exception during sync: {e}\n{traceback.format_exc()}")
                return False

        except Exception as e:
            self.logger.error(f"Unexpected error in sync thread: {e}\n{traceback.format_exc()}")
            return False

    def _load_settings(self):
        try:
            if os.path.exists(SETTINGS_FILE):
                with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
                    self.logger.info("Settings loaded successfully")
                    return settings
            else:
                self.logger.warning(f"Settings file not found: {SETTINGS_FILE}")
                return None
        except Exception as e:
            self.logger.error(f"Error loading settings: {e}\n{traceback.format_exc()}")
            return None

    def _load_last_sync_time(self):
        """Load the last sync timestamp"""
        try:
            if os.path.exists(LAST_SYNC_FILE):
                with open(LAST_SYNC_FILE, 'r') as f:
                    ts_str = f.read().strip()
                    if ts_str:
                        ts = float(ts_str)
                        self.last_sync_time = datetime.fromtimestamp(ts)
                        self.logger.info(f"Loaded last sync time: {self.last_sync_time}")
                    else:
                        self.logger.warning("Last sync file is empty")
                        self.last_sync_time = None
            else:
                self.logger.info("No previous sync time found")
                self.last_sync_time = None
        except (ValueError, OSError) as e:
            self.logger.warning(f"Failed to load last sync time: {e}")
            self.last_sync_time = None

    def _save_last_sync_time(self):
        """Save the last sync timestamp"""
        try:
            os.makedirs(BASE_DIR, exist_ok=True)
            with open(LAST_SYNC_FILE, 'w') as f:
                f.write(str(self.last_sync_time.timestamp()))
            self.logger.debug(f"Saved last sync time: {self.last_sync_time}")
        except Exception as e:
            self.logger.error(f"Failed to save last sync time: {e}")

# Service management functions with better error handling

def install_service():
    """Install the Windows service"""
    try:
        script_path = os.path.abspath(sys.argv[0])
        module_name = os.path.splitext(os.path.basename(script_path))[0]
        
        print(f"Installing service from: {script_path}")
        print(f"Module name: {module_name}")
        
        win32serviceutil.InstallService(
            pythonClassString=f'{module_name}.OfflineModeService',
            serviceName=OfflineModeService._svc_name_,
            displayName=OfflineModeService._svc_display_name_,
            description=OfflineModeService._svc_description_,
            startType=win32service.SERVICE_AUTO_START,
        )
        print(f"✓ Service '{OfflineModeService._svc_display_name_}' installed successfully")
        print("✓ Service set to start automatically with Windows")
        return True
    except Exception as e:
        print(f"✗ Failed to install service: {e}")
        return False

def start_service():
    """Start the Windows service"""
    try:
        win32serviceutil.StartService(OfflineModeService._svc_name_)
        print(f"✓ Service '{OfflineModeService._svc_display_name_}' started successfully")
        print(f"✓ Automatic sync every {SYNC_INTERVAL_MINUTES} minutes is now active")
        return True
    except Exception as e:
        print(f"✗ Failed to start service: {e}")
        return False

def stop_service():
    """Stop the Windows service"""
    try:
        win32serviceutil.StopService(OfflineModeService._svc_name_)
        print(f"✓ Service '{OfflineModeService._svc_display_name_}' stopped successfully")
        return True
    except Exception as e:
        print(f"✗ Failed to stop service: {e}")
        return False

def remove_service():
    """Remove the Windows service"""
    try:
        # Stop first
        try:
            stop_service()
            time.sleep(2)
        except Exception:
            pass  # Service might not be running
            
        win32serviceutil.RemoveService(OfflineModeService._svc_name_)
        print(f"✓ Service '{OfflineModeService._svc_display_name_}' removed successfully")
        return True
    except Exception as e:
        print(f"✗ Failed to remove service: {e}")
        return False

def debug_service():
    """Run service in debug mode (console mode)"""
    print("Running service in debug mode...")
    print("Press Ctrl+C to stop")
    
    try:
        service = OfflineModeService([])
        service.main()
    except KeyboardInterrupt:
        print("\nService stopped by user")

if __name__ == '__main__':
    
    if len(sys.argv) == 1:
        # Normal service mode
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(OfflineModeService)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        arg = sys.argv[1].lower()
        if arg == 'install':
            install_service()
        elif arg == 'start':
            start_service()
        elif arg == 'stop':
            stop_service()
        elif arg in ('remove', 'uninstall'):
            remove_service()
        elif arg == 'debug':
            debug_service()
        else:
            # Fall back to standard service utilities
            win32serviceutil.HandleCommandLine(OfflineModeService)