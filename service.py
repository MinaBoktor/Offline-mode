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

import appdirs

APP_NAME = "OfflineMode"

# Directories and files
BASE_DIR = os.path.join(os.environ.get('PROGRAMDATA', r'C:\ProgramData'), APP_NAME)
LOG_DIR = os.path.join(BASE_DIR, 'Logs')
SETTINGS_DIR = appdirs.user_data_dir(APP_NAME)
SETTINGS_FILE = os.path.join(SETTINGS_DIR, "settings.json")
LAST_SYNC_FILE = os.path.join(BASE_DIR, 'last_sync.txt')

SYNC_INTERVAL_HOURS = 12  # 12 hours default

class OfflineModeService(win32serviceutil.ServiceFramework):
    _svc_name_ = "OfflineModeService"
    _svc_display_name_ = "Offline Mode Background Service"
    _svc_description_ = "Automatically syncs Raindrop.io bookmarks every 12 hours"

    def __init__(self, args):
        super().__init__(args)
        self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
        self.is_running = True
        self.last_sync_time = None
        self.sync_lock = threading.Lock()
        self.sync_thread = None
        self.stop_event = threading.Event()

        # Setup logging
        os.makedirs(LOG_DIR, exist_ok=True)
        log_file = os.path.join(LOG_DIR, 'service.log')

        self.logger = logging.getLogger()
        self.logger.setLevel(logging.INFO)

        # Clear any existing handlers
        while self.logger.handlers:
            self.logger.handlers.pop()

        # File handler with rotation
        file_handler = logging.handlers.RotatingFileHandler(log_file, maxBytes=10*1024*1024, backupCount=5, encoding='utf-8')
        file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        self.logger.addHandler(file_handler)

        # Windows Event Log handler
        try:
            event_handler = logging.handlers.NTEventLogHandler(APP_NAME)
            event_handler.setFormatter(logging.Formatter('%(levelname)s - %(message)s'))
            self.logger.addHandler(event_handler)
        except Exception as e:
            # fallback to console if event log handler fails (unlikely in service)
            self.logger.error(f"Failed to add NTEventLogHandler: {e}")

        self.logger.info("Logging initialized")

    def SvcStop(self):
        """Called when service is asked to stop"""
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        self.logger.info("Service stop requested")

        self.is_running = False
        self.stop_event.set()  # Signal threads to stop

        # Wait for sync thread to finish
        if self.sync_thread and self.sync_thread.is_alive():
            self.logger.info("Waiting for sync thread to stop...")
            self.sync_thread.join(timeout=10)

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
            self.logger.error(f"Fatal error in service main loop: {e}\n{traceback.format_exc()}")
            raise

        servicemanager.LogInfoMsg("Offline Mode Background Service stopped.")

    def main(self):

        """Main loop running inside service"""
        self._load_last_sync_time()

        # If missed syncs (service was down for a long time), run catch-up sync
        if self._check_missed_syncs():
            self.logger.info("Running catch-up sync due to missed sync periods")
            self._run_sync_async()

        while self.is_running:
            try:
                if self._is_sync_time():
                    self.logger.info("Sync interval reached; starting sync")
                    self._run_sync_async()
                time.sleep(60)  # Check every minute

            except Exception as e:
                self.logger.error(f"Error in main loop: {e}\n{traceback.format_exc()}")
                time.sleep(60)

    def _is_sync_time(self):
        if not self.last_sync_time:
            return True  # No previous sync, run now

        now = datetime.now()
        elapsed_hours = (now - self.last_sync_time).total_seconds() / 3600
        return elapsed_hours >= SYNC_INTERVAL_HOURS

    def _check_missed_syncs(self):
        if not self.last_sync_time:
            self.logger.info("No previous sync time recorded; will sync now")
            return True

        now = datetime.now()
        elapsed_hours = (now - self.last_sync_time).total_seconds() / 3600
        self.logger.info(f"Hours since last sync: {elapsed_hours:.2f}")

        if elapsed_hours > SYNC_INTERVAL_HOURS:
            self.logger.info("Missed sync period detected")
            return True

        return False

    def _run_sync_async(self):
        with self.sync_lock:
            if self.sync_thread and self.sync_thread.is_alive():
                self.logger.info("Sync already running, skipping new sync request")
                return

            self.logger.info("Starting new sync thread")
            self.sync_thread = threading.Thread(target=self._run_sync, daemon=True)
            self.sync_thread.start()

    def _run_sync(self):
        try:
            self.logger.info("Sync process started")
            settings = self._load_settings()
            if not settings:
                self.logger.error("Settings missing or invalid - aborting sync")
                return False

            token = settings.get('token')
            path = settings.get('path')
            if not token or not path:
                self.logger.error("Missing 'token' or 'path' in settings - aborting sync")
                return False

            try:
                import offline
                offline.verify_directory_structure(path)

                success = offline.sync(
                    token,
                    path,
                    settings.get('resolution', '720'),
                    settings.get('delimiter', '#$@'),
                    settings.get('video', False),
                    self.stop_event
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
                self.logger.error(f"Failed to import 'offline' module: {e}")
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
        try:
            if os.path.exists(LAST_SYNC_FILE):
                with open(LAST_SYNC_FILE, 'r') as f:
                    ts = float(f.read().strip())
                    self.last_sync_time = datetime.fromtimestamp(ts)
                    self.logger.info(f"Loaded last sync time: {self.last_sync_time}")
            else:
                self.logger.info("No previous sync time found")
                self.last_sync_time = None
        except Exception as e:
            self.logger.warning(f"Failed to load last sync time: {e}")
            self.last_sync_time = None

    def _save_last_sync_time(self):
        try:
            os.makedirs(BASE_DIR, exist_ok=True)
            with open(LAST_SYNC_FILE, 'w') as f:
                f.write(str(self.last_sync_time.timestamp()))
            self.logger.info(f"Saved last sync time: {self.last_sync_time}")
        except Exception as e:
            self.logger.error(f"Failed to save last sync time: {e}")

# Service management helpers with correct install parameters

def install_service():
    try:
        # Use the fully qualified python class string: module.classname
        # Assuming this script is named service.py
        script_path = os.path.abspath(sys.argv[0])
        win32serviceutil.InstallService(
            pythonClassString=f'{os.path.splitext(os.path.basename(script_path))[0]}.OfflineModeService',
            serviceName=OfflineModeService._svc_name_,
            displayName=OfflineModeService._svc_display_name_,
            description=OfflineModeService._svc_description_,
            startType=win32service.SERVICE_AUTO_START,
        )
        print(f"Service '{OfflineModeService._svc_display_name_}' installed successfully and set to auto-start")
    except Exception as e:
        print(f"Failed to install service: {e}")

def start_service():
    try:
        win32serviceutil.StartService(OfflineModeService._svc_name_)
        print(f"Service '{OfflineModeService._svc_display_name_}' started successfully")
    except Exception as e:
        print(f"Failed to start service: {e}")

def stop_service():
    try:
        win32serviceutil.StopService(OfflineModeService._svc_name_)
        print(f"Service '{OfflineModeService._svc_display_name_}' stopped successfully")
    except Exception as e:
        print(f"Failed to stop service: {e}")

def remove_service():
    try:
        try:
            stop_service()
            time.sleep(2)
        except Exception:
            pass
        win32serviceutil.RemoveService(OfflineModeService._svc_name_)
        print(f"Service '{OfflineModeService._svc_display_name_}' removed successfully")
    except Exception as e:
        print(f"Failed to remove service: {e}")

if __name__ == '__main__':
    if len(sys.argv) == 1:
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
        else:
            win32serviceutil.HandleCommandLine(OfflineModeService)
