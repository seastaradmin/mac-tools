#!/usr/bin/env python3
"""
测试所有模块是否能正常导入
"""

import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_imports():
    """测试所有模块导入"""
    print("测试模块导入...")
    failed = []
    
    try:
        from config import MIMO_API_KEY, SCREENSHOT_DIR
        print("✓ config 模块导入成功")
    except Exception as e:
        print(f"✗ config 模块导入失败: {e}")
        failed.append("config")
    
    try:
        from screenshot.capture import ScreenCapture
        print("✓ ScreenCapture 模块导入成功")
    except Exception as e:
        print(f"✗ ScreenCapture 模块导入失败: {e}")
        failed.append("ScreenCapture")
    
    try:
        from screenshot.editor import ImageEditor
        print("✓ ImageEditor 模块导入成功")
    except Exception as e:
        print(f"✗ ImageEditor 模块导入失败: {e}")
        failed.append("ImageEditor")
    
    try:
        from speech.recorder import AudioRecorder
        print("✓ AudioRecorder 模块导入成功")
    except Exception as e:
        print(f"✗ AudioRecorder 模块导入失败: {e}")
        failed.append("AudioRecorder")
    
    try:
        from speech.recognizer import SpeechRecognizer
        print("✓ SpeechRecognizer 模块导入成功")
    except Exception as e:
        print(f"✗ SpeechRecognizer 模块导入失败: {e}")
        failed.append("SpeechRecognizer")
    
    try:
        from app_diagnostics import collect_diagnostics
        print("✓ app_diagnostics 模块导入成功")
    except Exception as e:
        print(f"✗ app_diagnostics 模块导入失败: {e}")
        failed.append("app_diagnostics")

    try:
        from macos_permissions import open_privacy_settings
        print("✓ macos_permissions 模块导入成功")
    except Exception as e:
        print(f"✗ macos_permissions 模块导入失败: {e}")
        failed.append("macos_permissions")
    
    try:
        from hotkeys.manager import HotkeyManager
        print("✓ HotkeyManager 模块导入成功")
    except Exception as e:
        print(f"✗ HotkeyManager 模块导入失败: {e}")
        failed.append("HotkeyManager")
    
    try:
        from PyQt6.QtWidgets import QApplication
        print("✓ PyQt6 模块导入成功")
    except Exception as e:
        print(f"✗ PyQt6 模块导入失败: {e}")
        failed.append("PyQt6")
    
    if failed:
        print(f"\n✗ 导入测试失败: {', '.join(failed)}")
        return False

    print("\n✓ 导入测试通过!")
    return True

if __name__ == "__main__":
    sys.exit(0 if test_imports() else 1)
