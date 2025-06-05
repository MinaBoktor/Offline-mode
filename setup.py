from setuptools import setup, find_packages
from setuptools.command.install import install
import os
import sys
import subprocess
import time

APP_NAME = "OfflineMode"
VERSION = "1.0"

class CustomInstallCommand(install):
    """Custom installation command that also installs and starts the service"""
    
    def run(self):
        # Run the standard installation first
        install.run(self)
        
        # Only run service installation on Windows
        if os.name == 'nt':
            self.install_and_start_service()
            self.create_shortcut()
    
    def install_and_start_service(self):
        """Install and start the Windows service automatically"""
        try:
            # Get the service executable path
            service_exe = self.find_service_executable()
            if not service_exe:
                print("Warning: Service executable not found, skipping service installation")
                return
            
            print("Installing OfflineMode background service...")
            
            # Install the service
            result = subprocess.run([service_exe, 'install'], 
                                  capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                print("✓ Service installed successfully")
                
                # Start the service
                print("Starting OfflineMode service...")
                time.sleep(2)  # Brief pause between install and start
                
                start_result = subprocess.run([service_exe, 'start'], 
                                            capture_output=True, text=True, timeout=30)
                
                if start_result.returncode == 0:
                    print("✓ Service started successfully")
                    print("✓ Automatic sync every 12 hours is now active")
                else:
                    print(f"Warning: Failed to start service: {start_result.stderr}")
                    print("You can start it manually using the service management tool")
            else:
                print(f"Warning: Failed to install service: {result.stderr}")
                print("You can install it manually using the service management tool")
                
        except subprocess.TimeoutExpired:
            print("Warning: Service installation timed out")
        except Exception as e:
            print(f"Warning: Error during service installation: {e}")
            print("You can install the service manually using the provided service.bat file")
    
    def find_service_executable(self):
        """Find the service executable in various possible locations"""
        possible_paths = [
            # Same directory as this script
            os.path.join(os.path.dirname(__file__), f"{APP_NAME}_service.exe"),
            # In a dist directory
            os.path.join(os.path.dirname(__file__), "dist", f"{APP_NAME}_service.exe"),
            # In the installation directory
            os.path.join(sys.prefix, "Scripts", f"{APP_NAME}_service.exe"),
            # In Program Files
            os.path.join(os.environ.get('PROGRAMFILES', 'C:\\Program Files'), APP_NAME, f"{APP_NAME}_service.exe"),
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                print(f"Found service executable at: {path}")
                return path
        
        return None

    def create_shortcut(self):
        """Create desktop shortcut"""
        try:
            import winshell
            from win32com.client import Dispatch

            desktop = winshell.desktop()
            path = os.path.join(desktop, f"{APP_NAME}.lnk")
            
            # Try to find the main executable
            possible_exe_paths = [
                os.path.join(os.path.dirname(__file__), f"{APP_NAME}.exe"),
                os.path.join(os.path.dirname(__file__), "dist", f"{APP_NAME}.exe"),
                os.path.join(sys.prefix, "Scripts", f"{APP_NAME}.exe"),
                os.path.join(os.environ.get('PROGRAMFILES', 'C:\\Program Files'), APP_NAME, f"{APP_NAME}.exe"),
            ]
            
            target = None
            for exe_path in possible_exe_paths:
                if os.path.exists(exe_path):
                    target = exe_path
                    break
            
            if not target:
                print("Warning: Could not find main executable for shortcut")
                return
                
            wDir = os.path.dirname(target)
            
            # Use icon if available
            icon = os.path.join(os.path.dirname(__file__), "offline.ico")
            if not os.path.exists(icon):
                icon = ""
                
            shell = Dispatch('WScript.Shell')
            shortcut = shell.CreateShortCut(path)
            shortcut.Targetpath = target
            shortcut.WorkingDirectory = wDir
            if icon:
                shortcut.IconLocation = icon
            shortcut.save()
            print(f"✓ Created desktop shortcut at {path}")
            
        except ImportError:
            print("Warning: Could not create shortcut (winshell not available)")
        except Exception as e:
            print(f"Warning: Failed to create shortcut: {e}")

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
    ],
    package_data={
        '': ['*.ico', '*.exe', '*.bat'],
    },
    entry_points={
        'console_scripts': [
            'offlinemode = settings_app:main',
        ],
    },
    data_files=[
        ('', ['offline.ico']),
    ],
    
    # Use custom install command
    cmdclass={
        'install': CustomInstallCommand,
    },

    options={
        'build_exe': {
            'includes': ['win32timezone'],
        },
    },
)