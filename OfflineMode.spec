# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['C:\\Users\\RexoL\\source\\repos\\Offline-mode\\settings_app.py'],
    pathex=[],
    binaries=[],
    datas=[('C:\\Users\\RexoL\\source\\repos\\Offline-mode\\offline.ico', '.'), ('C:\\Users\\RexoL\\source\\repos\\Offline-mode\\offline.py', '.')],
    hiddenimports=['pystray._win32', 'pystray._darwin', 'pystray._x11', 'concurrent.futures', 'threading', 'queue', 'concurrent_log_handler', 'monolith', 'pywin32', 'win32serviceutil', 'win32service', 'win32event', 'servicemanager', 'win32timezone', 'win32api', 'win32con', 'pywintypes', 'logging.handlers', 'appdirs', 'json', 'datetime'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='OfflineMode',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['C:\\Users\\RexoL\\source\\repos\\Offline-mode\\offline.ico'],
)
