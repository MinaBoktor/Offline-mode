import customtkinter as ctk
import json
import os
from tkinter import filedialog
from tkinter import messagebox
import offline
import threading
import sys
import queue
import time
import winreg
import atexit
import signal

import pystray
from PIL import Image
from plyer import notification
import appdirs

APP_NAME = "OfflineMode"
SETTINGS_DIR = appdirs.user_data_dir(APP_NAME)
os.makedirs(SETTINGS_DIR, exist_ok=True)
SETTINGS_FILE = os.path.join(SETTINGS_DIR, "settings.json")

# Global shutdown flag
_app_shutdown = threading.Event()
_active_sync_threads = []
_sync_lock = threading.Lock()

def _cleanup_on_exit():
    """Cleanup function called on application exit"""
    print("Application cleanup initiated")
    _app_shutdown.set()
    
    # Wait for active sync threads to finish
    with _sync_lock:
        for thread in _active_sync_threads[:]:
            if thread.is_alive():
                print(f"Waiting for sync thread to finish...")
                thread.join(timeout=3)  # Wait max 3 seconds per thread
    
    print("Application cleanup completed")

# Register cleanup handlers
atexit.register(_cleanup_on_exit)

def _signal_handler(signum, frame):
    """Handle shutdown signals"""
    print(f"Received signal {signum}, shutting down gracefully")
    _cleanup_on_exit()
    sys.exit(0)

# Register signal handlers
if hasattr(signal, 'SIGTERM'):
    signal.signal(signal.SIGTERM, _signal_handler)
if hasattr(signal, 'SIGINT'):
    signal.signal(signal.SIGINT, _signal_handler)

def main(command_queue=None):
    if command_queue is None:
        command_queue = queue.Queue()

    app = SettingsApp(command_queue)
    if '--service' not in sys.argv:
        app.mainloop()
    else:
        # Service mode runs without GUI
        while not _app_shutdown.is_set():
            time.sleep(1)

def add_to_startup():
    """Add the application to Windows startup"""
    try:
        key = winreg.HKEY_CURRENT_USER
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"

        with winreg.OpenKey(key, key_path, 0, winreg.KEY_WRITE) as reg_key:
            app_path = os.path.join(os.environ['PROGRAMFILES'], "OfflineMode", "OfflineMode.exe")
            winreg.SetValueEx(reg_key, "OfflineMode", 0, winreg.REG_SZ, app_path)
        return True
    except Exception as e:
        print(f"Failed to add to startup: {e}")
        return False

def remove_from_startup():
    """Remove the application from Windows startup"""
    try:
        key = winreg.HKEY_CURRENT_USER
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"

        with winreg.OpenKey(key, key_path, 0, winreg.KEY_WRITE) as reg_key:
            winreg.DeleteValue(reg_key, "OfflineMode")
        return True
    except Exception as e:
        print(f"Failed to remove from startup: {e}")
        return False

def load_settings():
    """Load settings from file"""
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                settings = json.load(f)
                # Ensure backward compatibility and add delimiter if missing
                return {
                    "token": settings.get("token", ""),
                    "path": settings.get("path", ""),
                    "video": settings.get("video", False),
                    "resolution": settings.get("resolution", "720"),
                    "delimiter": settings.get("delimiter", "#$@")  # Add default delimiter
                }
        except Exception as e:
            print(f"Error loading settings: {e}")
    
    return {
        "token": "",
        "path": "",
        "video": False,
        "resolution": "720",
        "delimiter": "#$@"  # Add default delimiter
    }

def save_settings(data):
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        print(f"Error saving settings: {e}")

def notify(title, message):
    try:
        notification.notify(
            title=title,
            message=message,
            app_icon=get_icon_path("offline.ico"),
            timeout=5
        )
    except Exception as e:
        print(f"Notification failed: {e}")

class SettingsApp(ctk.CTk):
    def __init__(self, command_queue):
        super().__init__()

        self.settings = load_settings()  # Fixed: removed 'self' parameter
        if self.settings["path"]:  # If path is already configured
            try:
                offline.verify_directory_structure(self.settings["path"])
            except Exception as e:
                print(f"Error verifying directory structure: {e}")

        try:
            self.iconbitmap(get_icon_path("offline.ico"))
        except Exception:
            pass  # Icon file not found, continue without it

        self.title("Offline Mode")
        self.geometry("400x480")
        self._is_running = True
        self._destroyed = False

        ctk.set_appearance_mode("system")
        ctk.set_default_color_theme("blue")

        # Initialize UI components
        self.token_entry = ctk.CTkEntry(self, width=300)
        self.token_entry.insert(0, self.settings["token"])

        self.path_entry = ctk.CTkEntry(self, width=280)
        self.path_entry.insert(0, self.settings["path"])

        self.delimiter_entry = ctk.CTkEntry(self, width=300)
        self.delimiter_entry.insert(0, self.settings.get("delimiter", "#$@"))  # Fixed: use get() method

        self.video_var = ctk.BooleanVar(value=self.settings["video"])
        self.video_checkbox = ctk.CTkCheckBox(self, text="Download Videos", variable=self.video_var)

        self.resolution_entry = ctk.CTkEntry(self, width=300)
        self.resolution_entry.insert(0, self.settings["resolution"])

        self.status_label = None
        self.command_queue = command_queue
        
        # Thread-safe sync management
        self.current_sync_thread = None
        self.current_stop_event = None
        self.sync_lock = threading.Lock()

        self.build_ui()
        self.protocol("WM_DELETE_WINDOW", self.hide_window)
        
        # Start queue processing
        self.after(200, self.process_queue)

    def is_in_startup(self):
        """Check if app is in Windows startup"""
        try:
            key = winreg.HKEY_CURRENT_USER
            key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
            with winreg.OpenKey(key, key_path, 0, winreg.KEY_READ) as reg_key:
                try:
                    winreg.QueryValueEx(reg_key, "OfflineMode")
                    return True
                except WindowsError:
                    return False
        except Exception:
            return False

    def toggle_startup(self):
        """Toggle Windows startup setting"""
        try:
            if self.startup_var.get():
                add_to_startup()
            else:
                remove_from_startup()
        except Exception as e:
            print(f"Error toggling startup: {e}")

    def build_ui(self):
        ctk.CTkLabel(self, text="Raindrop API Token:").pack(pady=(10, 0))
        self.token_entry.pack(pady=5)

        ctk.CTkLabel(self, text="Download Path:").pack(pady=(10, 0))
        path_frame = ctk.CTkFrame(self)
        path_frame.pack(pady=5, padx=10)

        self.path_entry.pack(in_=path_frame, side="left")
        ctk.CTkButton(path_frame, text="Browse", width=80, command=self.browse_path).pack(side="left", padx=5)

        ctk.CTkLabel(self, text="Video Resolution:").pack(pady=(10, 0))
        self.resolution_entry.pack(pady=5)

        self.video_checkbox.pack(pady=10)

        self.startup_var = ctk.BooleanVar(value=self.is_in_startup())
        self.startup_checkbox = ctk.CTkCheckBox(
            self,
            text="Start with Windows",
            variable=self.startup_var,
            command=self.toggle_startup
        )
        self.startup_checkbox.pack(pady=10)

        save_btn = ctk.CTkButton(
            self,
            text="Save Settings",
            width=180,
            height=40,
            font=ctk.CTkFont(size=16, weight="bold"),
            command=self.save
        )
        save_btn.pack(pady=10)

        sync_btn = ctk.CTkButton(
            self,
            text="Run Sync",
            width=180,
            height=40,
            font=ctk.CTkFont(size=16, weight="bold"),
            fg_color="#4caf50",
            hover_color="#45a049",
            command=self.run_sync
        )
        sync_btn.pack(pady=(0, 20))

    def browse_path(self):
        try:
            base_path = filedialog.askdirectory()
            if base_path:
                # Verify and create directory structure
                verified_path = offline.verify_directory_structure(base_path)
                # Update the path entry
                self.path_entry.delete(0, "end")
                self.path_entry.insert(0, verified_path)
        except Exception as e:
            messagebox.showerror("Error", f"Could not create directory structure: {e}")

    def save(self):
        try:
            settings = {
                "token": self.token_entry.get(),
                "path": self.path_entry.get(),
                "video": self.video_var.get(),
                "resolution": self.resolution_entry.get(),
                "delimiter": self.delimiter_entry.get()  # Fixed: added delimiter saving
            }
            save_settings(settings)

            if self.status_label:
                self.status_label.destroy()
            self.status_label = ctk.CTkLabel(self, text="✅ Settings saved!", text_color="green")
            self.status_label.pack()
        except Exception as e:
            print(f"Error saving settings: {e}")

    def run_sync(self):
        """Start sync operation with proper thread management"""
        # Check if already running or shutting down
        if _app_shutdown.is_set():
            print("Application is shutting down, cannot start sync")
            return
            
        with self.sync_lock:
            if self.current_sync_thread and self.current_sync_thread.is_alive():
                print("Sync already in progress - skipping")
                return

        # Verify path before sync
        try:
            verified_path = offline.verify_directory_structure(self.path_entry.get())
            self.path_entry.delete(0, "end")
            self.path_entry.insert(0, verified_path)
        except Exception as e:
            self._update_sync_status(False, f"Path verification failed: {e}")
            return

        # Clear previous status
        if self.status_label:
            self.status_label.destroy()

        # Create and configure status label before starting thread
        self.status_label = ctk.CTkLabel(self, text="🔄 Syncing...", text_color="orange")
        self.status_label.pack()
        self.update()  # Force UI update before thread starts

        # Create stop event for this sync
        self.current_stop_event = threading.Event()

        # Start sync thread with proper tracking
        self.current_sync_thread = threading.Thread(
            target=self._sync_thread,
            daemon=False  # Don't use daemon thread to ensure proper cleanup
        )
        
        # Register thread for cleanup
        with _sync_lock:
            _active_sync_threads.append(self.current_sync_thread)
        
        self.current_sync_thread.start()

    def _sync_thread(self):
        """Thread-safe sync execution"""
        try:
            # Check if shutdown was requested before starting
            if _app_shutdown.is_set() or (self.current_stop_event and self.current_stop_event.is_set()):
                self.after(0, self._update_sync_status, False, "Sync cancelled")
                return

            settings = {
                "token": self.token_entry.get(),
                "path": self.path_entry.get(),
                "video": self.video_var.get(),
                "resolution": self.resolution_entry.get(),
                "delimiter": self.delimiter_entry.get()  # Fixed: added delimiter
            }

            print("Starting sync operation...")
            
            # Run sync with stop event
            success = offline.sync(
                settings['token'],
                settings['path'],
                settings['resolution'],
                settings['delimiter'],  # Fixed: pass delimiter instead of empty string
                settings['video'],
                self.current_stop_event
            )
            
            # Update UI if not shutting down
            if not _app_shutdown.is_set() and not self._destroyed:
                if success:
                    self.after(0, self._update_sync_status, True, "Sync completed successfully")
                else:
                    self.after(0, self._update_sync_status, False, "Sync failed or was cancelled")
                    
        except Exception as e:
            print(f"Sync thread error: {e}")
            if not _app_shutdown.is_set() and not self._destroyed:
                self.after(0, self._update_sync_status, False, f"Sync error: {str(e)}")

    def _update_sync_status(self, success, message):
        """Thread-safe UI update method"""
        if self._destroyed or _app_shutdown.is_set():
            return
            
        try:
            if self.status_label:
                self.status_label.destroy()

            color = "green" if success else "red"
            prefix = "✅" if success else "❌"
            self.status_label = ctk.CTkLabel(
                self,
                text=f"{prefix} {message}",
                text_color=color
            )
            self.status_label.pack()
            self.update()  # Force immediate UI refresh
        except Exception as e:
            print(f"Error updating sync status: {e}")

    def hide_window(self):
        """Hide window instead of closing"""
        try:
            self.withdraw()
        except Exception as e:
            print(f"Error hiding window: {e}")

    def show_window(self):
        """Show and focus window"""
        try:
            self.deiconify()
            self.lift()
            self.attributes("-topmost", True)
            self.after(100, lambda: self.attributes("-topmost", False))
            self.focus_force()
        except Exception as e:
            print(f"Error showing window: {e}")

    def process_queue(self):
        """Process command queue with proper error handling"""
        if not self._is_running or _app_shutdown.is_set():
            return

        try:
            while not self.command_queue.empty():
                try:
                    cmd = self.command_queue.get_nowait()
                    if cmd == "show":
                        self.show_window()
                    elif cmd == "sync":
                        # Run sync in a separate thread to avoid blocking
                        sync_thread = threading.Thread(
                            target=self.run_sync,
                            daemon=True
                        )
                        sync_thread.start()
                    elif cmd == "quit":
                        self.quit_app()
                        return  # Don't schedule next check after quitting
                except queue.Empty:
                    break
                except Exception as e:
                    print(f"Error processing command: {e}")
        except Exception as e:
            print(f"Error in queue processing: {e}")

        if self._is_running and not _app_shutdown.is_set():
            try:
                self.after(200, self.process_queue)
            except Exception as e:
                print(f"Error scheduling queue processing: {e}")

    def quit_app(self):
        """Proper application shutdown with sync cancellation"""
        print("Application shutdown initiated")
        self._is_running = False
        _app_shutdown.set()

        # Signal current sync to stop
        with self.sync_lock:
            if self.current_stop_event:
                print("Signaling sync to stop...")
                self.current_stop_event.set()

        # Wait for sync thread to finish
        if self.current_sync_thread and self.current_sync_thread.is_alive():
            print("Waiting for sync thread to finish...")
            self.current_sync_thread.join(timeout=5)  # Wait max 5 seconds

        # Mark as destroyed before calling destroy to prevent UI updates
        self._destroyed = True

        # Properly destroy the window
        try:
            self.destroy()
        except Exception as e:
            print(f"Error destroying window: {e}")

        print("Application shutdown completed")

    def destroy(self):
        """Override destroy to ensure proper cleanup"""
        self._destroyed = True
        try:
            super().destroy()
        except Exception as e:
            print(f"Error in destroy: {e}")

# Global tray icon reference
tray_icon = None

def create_tray_icon(command_queue):
    """Create system tray icon with improved error handling"""
    global tray_icon

    # Clean up existing icon if any
    if tray_icon is not None:
        try:
            tray_icon.stop()
        except Exception as e:
            print(f"Error stopping existing tray icon: {e}")

    try:
        icon_image = Image.open(get_icon_path("offline.ico"))
    except Exception as e:
        print(f"Could not load icon: {e}")
        # Create a simple default icon
        icon_image = Image.new('RGB', (16, 16), color='blue')

    def on_quit(icon, item):
        """Quit handler with proper cleanup"""
        print("Tray quit requested")
        command_queue.put("quit")
        
        # Give time for application cleanup
        time.sleep(3)
        
        try:
            icon.stop()
        except Exception as e:
            print(f"Error stopping tray icon: {e}")
        
        # Force exit if needed
        print("Forcing application exit")
        os._exit(0)

    try:
        menu = pystray.Menu(
            pystray.MenuItem("Open", lambda: command_queue.put("show")),
            pystray.MenuItem("Sync Now", lambda: command_queue.put("sync")),
            pystray.MenuItem("Quit", on_quit)
        )

        tray_icon = pystray.Icon("OfflineMode", icon_image, "Offline Mode", menu)
        tray_icon.run_detached()
    except Exception as e:
        print(f"Error creating tray icon: {e}")

def get_icon_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
            return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

if __name__ == "__main__":
    try:
        if '--silent' in sys.argv or '--hidden' in sys.argv:
            command_queue = queue.Queue()
            create_tray_icon(command_queue)
            app = SettingsApp(command_queue)
            app.withdraw()  # Hide the main window
            app.mainloop()  # Keep running in the background
        else:
            # Normal GUI startup
            command_queue = queue.Queue()
            
            def run_app():
                try:
                    app = SettingsApp(command_queue)
                    app.mainloop()
                except Exception as e:
                    print(f"App error: {e}")
                finally:
                    _app_shutdown.set()
            
            app_thread = threading.Thread(target=run_app, daemon=False)
            app_thread.start()
            
            create_tray_icon(command_queue)
            
            # Wait for app thread to finish
            app_thread.join()
            
    except Exception as e:
        print(f"Main execution error: {e}")
    finally:
        _cleanup_on_exit()
        print("Application terminated")