# -*- mode: python ; coding: utf-8 -*-
import sys
import os
from PySide6 import QtCore
import platform

# Determine the current platform
current_platform = platform.system().lower()

# Get Qt plugin directories
qt_plugin_path = os.path.join(os.path.dirname(QtCore.__file__), "plugins")

# Specify the bin folder path
bin_folder = os.path.join(os.getcwd(), 'bin')

# Platform specific configurations
if current_platform == "windows":
    bin_include = [(os.path.join(bin_folder, 'win'), 'bin/win')]
    icon = os.path.join("icon", "win", "icon.ico")
elif current_platform == "darwin":
    bin_include = [(os.path.join(bin_folder, 'mac'), 'bin/mac')]
    icon = os.path.join("icon", "mac", "icon.icns")

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        *bin_include,  # Include platform-specific binaries
        ('info.json', '.'),  # Include info.json in root
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# Collect Qt plugins
qt_plugins = [
    ('platforms', os.path.join(qt_plugin_path, 'platforms')),
    ('styles', os.path.join(qt_plugin_path, 'styles')),
]

for plugin_type, plugin_path in qt_plugins:
    if os.path.exists(plugin_path):
        a.datas += Tree(plugin_path, prefix=os.path.join('PySide6', 'plugins', plugin_type))

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='mdu',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='mdu',
)

# macOS specific
if current_platform == "darwin":
    app = BUNDLE(
        coll,
        name='MDU YouTube Downloader.app',
        icon=icon,
        bundle_identifier='com.mdu.ytdownloader',
        info_plist={
            'CFBundleShortVersionString': "2024.12.22",
            'CFBundleVersion': "2024.12.22",
            'CFBundleName': 'MDU YouTube Downloader',
            'CFBundleDisplayName': 'MDU YouTube Downloader',
            'CFBundleIdentifier': 'com.mdu.ytdownloader',
            'CFBundlePackageType': 'APPL',
            'CFBundleSignature': '????',
            'LSMinimumSystemVersion': '10.13.0',
            'NSHighResolutionCapable': True,
        }
    )
