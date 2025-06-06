from setuptools import setup, find_packages
from setuptools.command.install import install
import os
import sys
import subprocess
import time
import shutil
import platform

APP_NAME = "OfflineMode"
VERSION = "1.0"

class CustomInstallCommand(install):
    """Custom installation command that also installs and starts the service"""
    
    def run(self):
        # Run the standard installation first
        install.run(self)
        
        # Only run service installation on Windows
        if platform.system() == 'Windows':
            try:
                self.install_service()
                self.create_shortcut()
                self.copy_assets()
            except Exception as e:
                print(f"Warning: Service setup encountered an error: {str(e)}")
                print("You may need to manually install the service using service.bat")
    
    def install_service(self):
        """Install and start the Windows service"""
        print("\nConfiguring OfflineMode background service...")
        
        # Find the service executable
        service_exe = self.find_service_executable()
        if not service_exe:
            print("Warning: Could not find service executable")
            return False
        
        print(f"Found service executable at: {service_exe}")
        
        # Ensure the service executable is in a permanent location
        target_dir = os.path.join(os.environ.get('PROGRAMFILES', 'C:\\Program Files'), APP_NAME)
        os.makedirs(target_dir, exist_ok=True)
        
        # Copy all necessary files to the target directory
        required_files = [
            service_exe,
            os.path.join(os.path.dirname(service_exe), f"{APP_NAME}.exe"),
            os.path.join(os.path.dirname(service_exe), "offline.ico"),
            os.path.join(os.path.dirname(service_exe), "manage_service.bat"),
            os.path.join(os.path.dirname(service_exe), "debug_service.bat"),
            os.path.join(os.path.dirname(service_exe), "README.txt")
        ]
        
        for src_file in required_files:
            if os.path.exists(src_file):
                dest_file = os.path.join(target_dir, os.path.basename(src_file))
                print(f"Copying {os.path.basename(src_file)} to {target_dir}")
                shutil.copy2(src_file, dest_file)
        
        # Install the service
        print("Installing service...")
        result = subprocess.run(
            [os.path.join(target_dir, f"{APP_NAME}_service.exe"), "install"],
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.returncode != 0:
            print(f"Service installation failed: {result.stderr}")
            return False
        
        print("✓ Service installed successfully")
        
        # Start the service
        print("Starting service...")
        time.sleep(2)  # Brief pause
        
        start_result = subprocess.run(
            [os.path.join(target_dir, f"{APP_NAME}_service.exe"), "start"],
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if start_result.returncode != 0:
            print(f"Warning: Service start failed: {start_result.stderr}")
            print("You can start it manually using manage_service.bat")
            return False
        
        print("✓ Service started successfully")
        print("✓ Automatic sync every 5 minutes is now active")
        return True
    
    def find_service_executable(self):
        """Find the service executable in various possible locations"""
        search_paths = [
            # Same directory as this script
            os.path.dirname(__file__),
            # In a dist directory
            os.path.join(os.path.dirname(__file__), "dist", "setup_package"),
            # In the build directory
            os.path.join(os.path.dirname(__file__), "build"),
            # In the installation directory
            os.path.join(sys.prefix, "Scripts"),
        ]
        
        for path in search_paths:
            exe_path = os.path.join(path, f"{APP_NAME}_service.exe")
            if os.path.exists(exe_path):
                return exe_path
        
        return None
    
    def copy_assets(self):
        """Copy required assets to the installation directory"""
        target_dir = os.path.join(os.environ.get('PROGRAMFILES', 'C:\\Program Files'), APP_NAME)
        os.makedirs(target_dir, exist_ok=True)
        
        assets = ["offline.ico"]
        for asset in assets:
            src = os.path.join(os.path.dirname(__file__), asset)
            if os.path.exists(src):
                shutil.copy2(src, target_dir)
    
    def create_shortcut(self):
        """Create desktop and start menu shortcuts"""
        try:
            import winshell
            from win32com.client import Dispatch
            
            # Find the main executable
            target_dir = os.path.join(os.environ.get('PROGRAMFILES', 'C:\\Program Files'), APP_NAME)
            target_exe = os.path.join(target_dir, f"{APP_NAME}.exe")
            
            if not os.path.exists(target_exe):
                print("Warning: Could not find main executable for shortcut")
                return
            
            # Create desktop shortcut
            desktop = winshell.desktop()
            shortcut_path = os.path.join(desktop, f"{APP_NAME}.lnk")
            
            shell = Dispatch('WScript.Shell')
            shortcut = shell.CreateShortCut(shortcut_path)
            shortcut.TargetPath = target_exe
            shortcut.WorkingDirectory = target_dir
            shortcut.IconLocation = os.path.join(target_dir, "offline.ico")
            shortcut.save()
            print(f"✓ Created desktop shortcut at {shortcut_path}")
            
            # Create start menu shortcut
            start_menu = winshell.programs()
            start_menu_dir = os.path.join(start_menu, APP_NAME)
            os.makedirs(start_menu_dir, exist_ok=True)
            
            start_shortcut = os.path.join(start_menu_dir, f"{APP_NAME}.lnk")
            shortcut = shell.CreateShortCut(start_shortcut)
            shortcut.TargetPath = target_exe
            shortcut.WorkingDirectory = target_dir
            shortcut.IconLocation = os.path.join(target_dir, "offline.ico")
            shortcut.save()
            
        except Exception as e:
            print(f"Warning: Could not create shortcuts: {str(e)}")

setup(
    name=APP_NAME,
    version=VERSION,
    author="Myna LLC",
    author_email="Magedmina46@email.com",
    description="Offline Mode saves local copy of Raindrop.io bookmarks with automatic sync service",
    
    packages=find_packages(),
    install_requires=[
        'customtkinter>=5.2.0',
        'pystray>=0.19.3',
        'Pillow>=10.0.0',
        'plyer>=2.1.0',
        'requests>=2.31.0',
        'yt-dlp>=2023.11.16',
        'pywin32>=306;platform_system=="Windows"',
        'winshell>=0.6;platform_system=="Windows"',
        'appdirs>=1.4.4',
        'monolith>=2.6.0',
        'concurrent-log-handler>=0.9.24',
    ],
    package_data={
        '': ['*.ico', '*.exe', '*.bat', '*.py'],
    },
    entry_points={
        'gui_scripts': [
            'offlinemode = settings_app:main',
        ],
    },
    data_files=[
        ('', ['offline.ico', 'service.py', 'offline.py', 'web.py', 'youtube.py']),
    ],
    
    # Use custom install command
    cmdclass={
        'install': CustomInstallCommand,
    },
    python_requires='>=3.8',
)