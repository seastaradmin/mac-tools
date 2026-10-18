"""Runtime diagnostics shown from the menu-bar app."""

from pathlib import Path
from typing import Callable, Optional

from app_metadata import APP_BUNDLE_IDENTIFIER, APP_NAME, APP_VERSION
from config import AUDIO_DIR, CONFIG_FILE, MIMO_API_KEY, SCREENSHOT_DIR
from hotkeys.manager import is_accessibility_trusted
from macos_permissions import is_input_monitoring_trusted


def is_screen_recording_trusted() -> Optional[bool]:
    try:
        from Quartz import CGPreflightScreenCaptureAccess
        return bool(CGPreflightScreenCaptureAccess())
    except Exception:
        return None


def _permission_status(value: Optional[bool]) -> str:
    if value is True:
        return "已允许"
    if value is False:
        return "需要配置"
    return "无法检测"


def _path_status(path: Path) -> str:
    return "可写" if path.exists() and path.is_dir() else "未创建"


def collect_diagnostics(
    accessibility_checker: Callable[[], bool] = is_accessibility_trusted,
    input_monitoring_checker: Callable[[], bool] = is_input_monitoring_trusted,
    screen_checker: Callable[[], Optional[bool]] = is_screen_recording_trusted,
) -> list[tuple[str, str]]:
    return [
        ("应用", f"{APP_NAME} {APP_VERSION}"),
        ("Bundle ID", APP_BUNDLE_IDENTIFIER),
        ("辅助功能", _permission_status(accessibility_checker())),
        ("输入监控", _permission_status(input_monitoring_checker())),
        ("屏幕录制", _permission_status(screen_checker())),
        ("麦克风", "首次录音时由系统请求"),
        ("语音识别 API", "已配置" if MIMO_API_KEY else "未配置"),
        ("配置文件", str(CONFIG_FILE)),
        ("截图目录", f"{SCREENSHOT_DIR}（{_path_status(SCREENSHOT_DIR)}）"),
        ("音频缓存", f"{AUDIO_DIR}（{_path_status(AUDIO_DIR)}）"),
    ]


def format_diagnostics_report(items: list[tuple[str, str]]) -> str:
    return "\n".join(f"{label}: {value}" for label, value in items)
