# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['C:\\Users\\RexoL\\source\\repos\\Offline-mode\\service.py'],
    pathex=[],
    binaries=[],
    datas=[('C:\\Users\\RexoL\\source\\repos\\Offline-mode\\offline.ico', '.'), ('C:\\Users\\RexoL\\source\\repos\\Offline-mode\\offline.py', '.'), ('C:\\Users\\RexoL\\source\\repos\\Offline-mode\\web.py', '.'), ('C:\\Users\\RexoL\\source\\repos\\Offline-mode\\youtube.py', '.')],
    hiddenimports=['win32timezone', 'win32service', 'win32event', 'servicemanager', 'concurrent_log_handler', 'pystray._win32', 'pywintypes'],
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
    name='OfflineMode_service',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['C:\\Users\\RexoL\\source\\repos\\Offline-mode\\offline.ico'],
)
