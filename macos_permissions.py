"""Small macOS permission helpers for TCC settings pages."""

import subprocess
import sys


PRIVACY_URLS = {
    "accessibility": "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility",
    "input_monitoring": "x-apple.systempreferences:com.apple.preference.security?Privacy_ListenEvent",
    "screen_recording": "x-apple.systempreferences:com.apple.preference.security?Privacy_ScreenCapture",
    "microphone": "x-apple.systempreferences:com.apple.preference.security?Privacy_Microphone",
}


def open_privacy_settings(permission: str) -> bool:
    """Open the matching macOS Privacy & Security settings pane."""
    url = PRIVACY_URLS.get(permission)
    if sys.platform != "darwin" or not url:
        return False

    try:
        subprocess.run(["open", url], check=False)
        return True
    except Exception:
        return False


def prompt_accessibility_permission() -> bool:
    """Ask macOS to show the Accessibility trust prompt when possible."""
    if sys.platform != "darwin":
        return True

    try:
        from ApplicationServices import (
            AXIsProcessTrusted,
            AXIsProcessTrustedWithOptions,
            kAXTrustedCheckOptionPrompt,
        )

        if AXIsProcessTrusted():
            return True
        options = {kAXTrustedCheckOptionPrompt: True}
        return bool(AXIsProcessTrustedWithOptions(options))
    except Exception:
        return False


def is_input_monitoring_trusted() -> bool:
    """Return whether macOS allows this app to listen to keyboard input."""
    if sys.platform != "darwin":
        return True

    try:
        from Quartz import CGPreflightListenEventAccess
        return bool(CGPreflightListenEventAccess())
    except Exception:
        return False


def prompt_input_monitoring_permission() -> bool:
    """Ask macOS to register/request Input Monitoring permission when possible."""
    if sys.platform != "darwin":
        return True

    try:
        from Quartz import CGPreflightListenEventAccess, CGRequestListenEventAccess

        if CGPreflightListenEventAccess():
            return True
        return bool(CGRequestListenEventAccess())
    except Exception:
        return False


def prompt_screen_recording_permission() -> bool:
    """Ask macOS to register/request Screen Recording permission when possible."""
    if sys.platform != "darwin":
        return True

    try:
        from Quartz import CGPreflightScreenCaptureAccess, CGRequestScreenCaptureAccess

        if CGPreflightScreenCaptureAccess():
            return True
        return bool(CGRequestScreenCaptureAccess())
    except Exception:
        return False
