"""
配置文件 - Mac截图语音工具
"""

import os
import json
import sys
from pathlib import Path

from app_metadata import APP_NAME

# 项目根目录
PROJECT_ROOT = Path(__file__).parent

def _is_bundled_app() -> bool:
    return bool(getattr(sys, "frozen", False))

def _user_library_dir(name: str) -> Path:
    return Path.home() / "Library" / name / APP_NAME

def _pictures_dir() -> Path:
    return Path.home() / "Pictures" / APP_NAME

def _ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path

if _is_bundled_app():
    CONFIG_DIR = _ensure_dir(_user_library_dir("Application Support"))
    SCREENSHOT_DIR = _ensure_dir(_pictures_dir())
    TEMP_DIR = _ensure_dir(_user_library_dir("Caches") / "temp")
    MODEL_CACHE_DIR = _ensure_dir(_user_library_dir("Caches") / "models")
else:
    CONFIG_DIR = PROJECT_ROOT
    SCREENSHOT_DIR = _ensure_dir(PROJECT_ROOT / "screenshots")
    TEMP_DIR = _ensure_dir(PROJECT_ROOT / "temp")
    MODEL_CACHE_DIR = _ensure_dir(PROJECT_ROOT / "models" / "cache")

# 配置文件路径
CONFIG_FILE = CONFIG_DIR / "user_config.json"
CLIPBOARD_HISTORY_FILE = CONFIG_DIR / "clipboard_history.json"

# 音频临时文件目录
AUDIO_DIR = _ensure_dir(TEMP_DIR / "audio")

# 用户配置
def load_user_config():
    """加载用户配置"""
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_user_config(config):
    """保存用户配置"""
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False

# 加载用户配置
_user_config = load_user_config()

# MiMo API配置
# API Key 只能来自用户配置或环境变量；不要在客户端中内置服务密钥。
MIMO_API_KEY = (
    _user_config.get("mimo_api_key", "")
    or os.environ.get("MIMO_API_KEY", "")
)
MIMO_BASE_URL = "https://token-plan-cn.xiaomimimo.com/v1"
MIMO_ASR_MODEL = "mimo-v2.5-asr"

# 本地润色模型配置
# 可选: "TinyLlama/TinyLlama-1.1B-Chat-v1.0", "microsoft/phi-2" 等
POLISH_MODEL_NAME = "TinyLlama/TinyLlama-1.1B-Chat-v1.0"

# 快捷键配置
DEFAULT_HOTKEYS = {
    "screenshot": "<cmd>+<shift>+s",  # 截图快捷键
    "voice_input": "<fn>",  # 语音输入快捷键
    "clipboard_history": "<cmd>+<shift>+h",  # 剪贴板历史
}

DEFAULT_CLIPBOARD_HISTORY_LIMIT = 50
DEFAULT_CLIPBOARD_TEXT_MAX_LENGTH = 10000

# 音频配置
AUDIO_SAMPLE_RATE = 16000
AUDIO_CHANNELS = 1
AUDIO_CHUNK = 1024
AUDIO_FORMAT_BITS = 16

# 编辑器配置
EDITOR_DEFAULT_COLOR = "#FF0000"  # 默认画笔颜色（红色）
EDITOR_DEFAULT_LINE_WIDTH = 3  # 默认线条宽度
EDITOR_CANVAS_MARGIN = 50  # 画布边距

# 支持的音频格式
SUPPORTED_AUDIO_FORMATS = ["wav", "mp3"]
AUDIO_MIME_TYPES = {
    "wav": "audio/wav",
    "mp3": "audio/mpeg",
}

# 编辑器工具类型
class EditorTool:
    PEN = "pen"
    RECTANGLE = "rectangle"
    CIRCLE = "circle"
    ARROW = "arrow"
    TEXT = "text"
    SELECT = "select"
