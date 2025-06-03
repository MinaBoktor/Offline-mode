# service.py
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
from datetime import datetime, timedelta

try:
    from pywin32 import win32timezone
except ImportError:
    # Fallback for systems where pywin32 isn't properly installed
    import win32timezone

class OfflineModeService(win32serviceutil.ServiceFramework):
    _svc_name_ = "OfflineModeService"
    _svc_display_name_ = "Offline Mode Background Service"
    
    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
        self.is_running = True
        self.command_queue = queue.Queue()
        self.last_sync_time = None
        self.sync_lock = threading.Lock()
        
        # Configure logging
        log_dir = os.path.join(os.environ['PROGRAMDATA'], 'OfflineMode', 'Logs')
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, 'service.log')
        logging.basicConfig(
            filename=log_file,
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger()

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        self.is_running = False
        self.command_queue.put("quit")
        
        # Give threads time to clean up
        time.sleep(2)
        
        win32event.SetEvent(self.hWaitStop)
        servicemanager.LogInfoMsg("Service stopping gracefully")

    def SvcDoRun(self):
        servicemanager.LogMsg(
            servicemanager.EVENTLOG_INFORMATION_TYPE,
            servicemanager.PYS_SERVICE_STARTED,
            (self._svc_name_, '')
        )
        self.logger.info("Service started")
        self.main()

    def main(self):
        try:
            from settings_app import SettingsApp
            self.logger.info("Importing SettingsApp")
            
            # Load last sync time from file
            self._load_last_sync_time()
            
            # Check if we need to run sync immediately (catch up)
            self._check_missed_syncs()
            
            # Start the sync scheduler thread
            scheduler_thread = threading.Thread(
                target=self._run_scheduler,
                daemon=True
            )
            scheduler_thread.start()
            
            # Run in a separate thread to prevent blocking
            app_thread = threading.Thread(
                target=self.run_app,
                daemon=True
            )
            app_thread.start()
            
            while self.is_running:
                time.sleep(10)
                
        except Exception as e:
            self.logger.error(f"Service error: {str(e)}")
            raise

    def run_app(self):
        try:
            from settings_app import SettingsApp
            app = SettingsApp(self.command_queue)
            self.logger.info("SettingsApp initialized")
            
            # For service mode, don't show GUI
            if '--service' in sys.argv:
                app.withdraw()
                
            app.mainloop()
            
        except Exception as e:
            self.logger.error(f"App error: {str(e)}")
            raise

    def _run_scheduler(self):
        """Run the sync scheduler in a loop"""
        while self.is_running:
            now = datetime.now()
            
            # Calculate next sync time (12 hours from last sync or now if first time)
            if self.last_sync_time:
                next_sync = self.last_sync_time + timedelta(hours=12)
            else:
                next_sync = now
            
            # If next sync is in the past, run immediately
            if next_sync <= now:
                self._run_sync()
                next_sync = datetime.now() + timedelta(hours=12)
            else:
                # Wait until next sync time
                wait_seconds = (next_sync - now).total_seconds()
                self.logger.info(f"Next sync scheduled at {next_sync} (in {wait_seconds/3600:.1f} hours)")
                
                # Wait in small intervals to allow for service stop
                while wait_seconds > 0 and self.is_running:
                    sleep_time = min(60, wait_seconds)  # Check every minute at most
                    time.sleep(sleep_time)
                    wait_seconds -= sleep_time
            
            if not self.is_running:
                break

    def _run_sync(self):
        """Run the sync process if not already running"""
        with self.sync_lock:
            self.logger.info("Starting scheduled sync")
            self.command_queue.put("sync")
            self.last_sync_time = datetime.now()
            self._save_last_sync_time()
            self.logger.info(f"Sync completed at {self.last_sync_time}")

    def _load_last_sync_time(self):
        """Load last sync time from file"""
        try:
            sync_file = os.path.join(os.environ['PROGRAMDATA'], 'OfflineMode', 'last_sync.txt')
            if os.path.exists(sync_file):
                with open(sync_file, 'r') as f:
                    timestamp = float(f.read())
                    self.last_sync_time = datetime.fromtimestamp(timestamp)
                    self.logger.info(f"Loaded last sync time: {self.last_sync_time}")
        except Exception as e:
            self.logger.warning(f"Could not load last sync time: {str(e)}")
            self.last_sync_time = None

    def _save_last_sync_time(self):
        """Save last sync time to file"""
        try:
            sync_dir = os.path.join(os.environ['PROGRAMDATA'], 'OfflineMode')
            os.makedirs(sync_dir, exist_ok=True)
            sync_file = os.path.join(sync_dir, 'last_sync.txt')
            
            with open(sync_file, 'w') as f:
                f.write(str(self.last_sync_time.timestamp()))
        except Exception as e:
            self.logger.error(f"Could not save last sync time: {str(e)}")

    def _check_missed_syncs(self):
        """Check if any syncs were missed while the service was stopped"""
        if not self.last_sync_time:
            return
            
        now = datetime.now()
        time_since_last_sync = now - self.last_sync_time
        hours_since_last_sync = time_since_last_sync.total_seconds() / 3600
        
        # If more than 12 hours since last sync, we missed at least one
        if hours_since_last_sync > 12:
            self.logger.info(f"Detected missed sync ({hours_since_last_sync:.1f} hours since last sync)")
            self._run_sync()

if __name__ == '__main__':
    if len(sys.argv) == 1:
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(OfflineModeService)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        win32serviceutil.HandleCommandLine(OfflineModeService)