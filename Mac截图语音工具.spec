# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller打包配置文件
"""

import sys
from pathlib import Path

project_root = Path(SPECPATH)
sys.path.insert(0, str(project_root))

from app_metadata import (
    APP_BUNDLE_IDENTIFIER,
    APP_BUNDLE_NAME,
    APP_VERSION,
)

block_cipher = None

def keep_release_file(item):
    name = item[0]
    unused_qt_parts = [
        'PyQt6/Qt6/lib/QtPdf.framework',
        'PyQt6/Qt6/plugins/generic/libqtuiotouchplugin.dylib',
        'PyQt6/Qt6/plugins/iconengines/libqsvgicon.dylib',
        'PyQt6/Qt6/plugins/imageformats/libqmacjp2.dylib',
        'PyQt6/Qt6/plugins/imageformats/libqmacheif.dylib',
        'PyQt6/Qt6/plugins/imageformats/libqpdf.dylib',
        'PyQt6/Qt6/plugins/imageformats/libqsvg.dylib',
        'PyQt6/Qt6/plugins/imageformats/libqtga.dylib',
        'PyQt6/Qt6/plugins/imageformats/libqtiff.dylib',
        'PyQt6/Qt6/plugins/imageformats/libqwbmp.dylib',
        'PyQt6/Qt6/plugins/imageformats/libqwebp.dylib',
        'PyQt6/Qt6/plugins/platforms/libqminimal.dylib',
        'PyQt6/Qt6/plugins/platforms/libqoffscreen.dylib',
        'QtPdf',
    ]
    return not any(name == part or name.startswith(part + '/') for part in unused_qt_parts)

a = Analysis(
    ['main.py'],
    pathex=[str(project_root)],
    binaries=[],
    datas=[
        ('config.py', '.'),
        ('app_metadata.py', '.'),
    ],
    hiddenimports=[
        'PyQt6',
        'PyQt6.QtWidgets',
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'ApplicationServices',
        'AppKit',
        'Foundation',
        'Quartz',
        'objc',
        'PIL',
        'pyaudio',
        'pynput',
        'pynput.keyboard',
        'pynput.mouse',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib',
        'scipy',
        'pandas',
        'cv2',
        'numpy',
        'torch',
        'transformers',
        'openai',
        'httpx',
        'httpcore',
        'pydantic',
        'pydantic_core',
        'rich',
        'pygments',
        'anyio',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Mac截图语音工具',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=True,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

release_binaries = [item for item in a.binaries if keep_release_file(item)]
release_datas = [item for item in a.datas if keep_release_file(item)]

coll = COLLECT(
    exe,
    release_binaries,
    a.zipfiles,
    release_datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Mac截图语音工具',
)

app = BUNDLE(
    coll,
    name='Mac截图语音工具.app',
    icon='icon.icns',
    bundle_identifier=APP_BUNDLE_IDENTIFIER,
    info_plist={
        'CFBundleName': APP_BUNDLE_NAME,
        'CFBundleDisplayName': APP_BUNDLE_NAME,
        'CFBundleVersion': APP_VERSION,
        'CFBundleShortVersionString': APP_VERSION,
        'LSUIElement': True,
        'NSHighResolutionCapable': True,
        'NSMicrophoneUsageDescription': '需要麦克风权限来进行语音录音',
        'NSScreenCaptureUsageDescription': '需要屏幕录制权限来进行截图',
        'NSAccessibilityUsageDescription': '需要辅助功能权限来监听全局快捷键',
        'LSMinimumSystemVersion': '10.15',
        'LSApplicationCategoryType': 'public.app-category.utilities',
    },
)
