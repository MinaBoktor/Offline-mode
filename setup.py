from setuptools import setup, find_packages
import os
import sys

APP_NAME = "OfflineMode"
VERSION = "1.0"


# Only create shortcut on Windows during installation
if os.name == 'nt' and 'install' in sys.argv:
    import winshell
    from win32com.client import Dispatch

    def create_shortcut():
        try:
            desktop = winshell.desktop()
            path = os.path.join(desktop, f"{APP_NAME}.lnk")
            target = os.path.join(os.environ['PROGRAMFILES'], APP_NAME, f"{APP_NAME}.exe")
            wDir = os.path.join(os.environ['PROGRAMFILES'], APP_NAME)
            
            # Use a default icon if specific one doesn't exist
            icon = os.path.join(os.path.dirname(__file__), "offline.ico")
            if not os.path.exists(icon):
                icon = ""
                
            shell = Dispatch('WScript.Shell')
            shortcut = shell.CreateShortCut(path)
            shortcut.Targetpath = target
            shortcut.WorkingDirectory = wDir
            shortcut.IconLocation = icon
            shortcut.save()
            print(f"Created desktop shortcut at {path}")
        except Exception as e:
            print(f"Failed to create shortcut: {e}")

setup(
    name=APP_NAME,
    version=VERSION,
    author="Myna LLC",
    author_email="Magedmina46@email.com",
    description="Offline Mode saves local copy of Raindrop.io bookmarks",
    
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
        '': ['*.ico'],
    },
    entry_points={
        'console_scripts': [
            'offlinemode = settings_app:main',
        ],
    },
    data_files=[
        ('', ['offline.ico']),
    ],

    options={
        'build_exe': {
            'includes': ['win32timezone'],
        },
    },
)