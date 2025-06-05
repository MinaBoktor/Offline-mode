import unittest
import time
from datetime import datetime, timedelta
from service import OfflineModeService

class DummyOfflineModeService(OfflineModeService):
    def __init__(self):
        # Bypass base class init
        self.is_running = True
        self.last_sync_time = None
        self.sync_lock = None
        self.sync_thread = None
        self.logger = type('', (), {'info': print, 'error': print, 'warning': print})()  # Mock logger

    def _run_sync(self):
        print("[Test] Simulating sync operation")
        self.last_sync_time = datetime.now()
        return True

    def _load_settings(self):
        return {
            "token": "dummy_token",
            "path": "dummy_path",
            "resolution": "720",
            "delimiter": "#$@",
            "video": False
        }

    def _save_last_sync_time(self):
        print(f"[Test] Saved sync time: {self.last_sync_time}")

class SyncServiceTest(unittest.TestCase):
    def setUp(self):
        self.service = DummyOfflineModeService()

    def test_first_time_sync_required(self):
        self.service.last_sync_time = None
        self.assertTrue(self.service._is_sync_time(), "First sync should always trigger")

    def test_no_sync_needed_within_interval(self):
        self.service.last_sync_time = datetime.now()
        self.assertFalse(self.service._is_sync_time(), "No sync should be required within 5 minutes")

    def test_sync_needed_after_interval(self):
        self.service.last_sync_time = datetime.now() - timedelta(minutes=6)
        self.assertTrue(self.service._is_sync_time(), "Sync should trigger after 5 minutes")

    def test_check_missed_syncs_none(self):
        self.service.last_sync_time = None
        self.assertTrue(self.service._check_missed_syncs())

    def test_check_missed_syncs_recent(self):
        self.service.last_sync_time = datetime.now() - timedelta(hours=1)
        self.assertFalse(self.service._check_missed_syncs())

    def test_check_missed_syncs_old(self):
        self.service.last_sync_time = datetime.now() - timedelta(hours=13)
        self.assertTrue(self.service._check_missed_syncs())

    def test_run_sync_updates_time(self):
        self.service.last_sync_time = datetime.now() - timedelta(hours=13)
        self.assertTrue(self.service._run_sync())
        self.assertIsNotNone(self.service.last_sync_time)

if __name__ == "__main__":
    unittest.main()
