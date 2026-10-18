"""
通用语音输入模块 — 将识别结果放入剪贴板
无需辅助功能权限，稳定可靠
"""

import subprocess
import sys
import time


def copy_to_clipboard(text: str):
    """将文本复制到系统剪贴板（pbcopy，无需任何权限）"""
    if not text:
        return False
    try:
        proc = subprocess.Popen(["pbcopy"], stdin=subprocess.PIPE)
        proc.communicate(input=text.encode("utf-8"), timeout=5)
        return proc.returncode == 0
    except Exception as e:
        print(f"[VoiceInput] 剪贴板写入失败: {e}")
        return False


def _activate_target_app(target_bundle_id: str | None):
    if not target_bundle_id or sys.platform != "darwin":
        return False
    try:
        from AppKit import NSApplicationActivateIgnoringOtherApps, NSRunningApplication

        apps = NSRunningApplication.runningApplicationsWithBundleIdentifier_(target_bundle_id)
        if not apps:
            print(f"[VoiceInput] 目标应用未运行: {target_bundle_id}")
            return False
        apps[0].activateWithOptions_(NSApplicationActivateIgnoringOtherApps)
        time.sleep(0.12)
        return True
    except Exception as e:
        print(f"[VoiceInput] 激活目标应用失败: {e}")
        return False


def _paste_with_quartz():
    if sys.platform != "darwin":
        return False
    try:
        import Quartz

        source = Quartz.CGEventSourceCreate(Quartz.kCGEventSourceStateHIDSystemState)
        for key_down in (True, False):
            event = Quartz.CGEventCreateKeyboardEvent(source, 9, key_down)
            Quartz.CGEventSetFlags(event, Quartz.kCGEventFlagMaskCommand)
            Quartz.CGEventPost(Quartz.kCGHIDEventTap, event)
            time.sleep(0.03)
        return True
    except Exception as e:
        print(f"[VoiceInput] Quartz 粘贴失败: {e}")
        return False


def _paste_with_osascript():
    try:
        result = subprocess.run(
            ["osascript", "-e", 'tell application "System Events" to keystroke "v" using command down'],
            capture_output=True, text=True, timeout=3
        )
        if result.returncode != 0:
            stderr = (result.stderr or "").strip()
            print(f"[VoiceInput] AppleScript 粘贴失败: {stderr or result.returncode}")
            return False
        return True
    except Exception as e:
        print(f"[VoiceInput] AppleScript 粘贴异常: {e}")
        return False


def type_text(text: str, method: str = "auto", target_bundle_id: str | None = None):
    """
    将文本输入到当前焦点应用
    优先尝试模拟粘贴，失败则仅复制到剪贴板
    """
    if not text:
        return "empty"

    # 先确保文本在剪贴板中
    copied = copy_to_clipboard(text)
    if not copied:
        print(f"[VoiceInput] 输入失败: {text[:40]}")
        return "failed"

    _activate_target_app(target_bundle_id)
    if _paste_with_quartz() or _paste_with_osascript():
        print(f"[VoiceInput] 已粘贴: {text[:40]}")
        return "pasted"

    # 粘贴失败（需要辅助功能权限），文本已在剪贴板中
    print(f"[VoiceInput] 已复制到剪贴板（需手动 Cmd+V）: {text[:40]}")
    return "copied"
