import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


def load_config_module(name, home, frozen):
    spec = importlib.util.spec_from_file_location(name, Path("config.py"))
    module = importlib.util.module_from_spec(spec)
    with patch("pathlib.Path.home", return_value=Path(home)):
        if frozen:
            with patch("sys.frozen", True, create=True):
                spec.loader.exec_module(module)
        else:
            spec.loader.exec_module(module)
    return module


class ConfigPathTests(unittest.TestCase):

    def test_bundled_app_uses_macos_user_directories(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = load_config_module("config_bundled_test", tmp, frozen=True)
            home = Path(tmp)

            self.assertEqual(
                config.CONFIG_FILE,
                home / "Library" / "Application Support" / "Mac Tools" / "user_config.json",
            )
            self.assertEqual(
                config.SCREENSHOT_DIR,
                home / "Pictures" / "Mac Tools",
            )
            self.assertEqual(
                config.AUDIO_DIR,
                home / "Library" / "Caches" / "Mac Tools" / "temp" / "audio",
            )
            self.assertEqual(
                config.MODEL_CACHE_DIR,
                home / "Library" / "Caches" / "Mac Tools" / "models",
            )
            self.assertTrue(config.AUDIO_DIR.exists())

    def test_source_mode_keeps_project_local_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = load_config_module("config_source_test", tmp, frozen=False)

            self.assertEqual(config.CONFIG_FILE, config.PROJECT_ROOT / "user_config.json")
            self.assertEqual(config.SCREENSHOT_DIR, config.PROJECT_ROOT / "screenshots")

    def test_config_does_not_embed_api_key(self):
        config_source = Path("config.py").read_text(encoding="utf-8")

        self.assertNotIn("_BUILTIN_API_KEY", config_source)
        self.assertNotIn("tp-", config_source)

    def test_project_user_config_keeps_safe_defaults(self):
        config = json.loads(Path("user_config.json").read_text(encoding="utf-8"))

        self.assertEqual(config.get("mimo_api_key"), "")
        self.assertEqual(config.get("hotkey_screenshot"), "<cmd>+<shift>+s")
        self.assertEqual(config.get("hotkey_voice_input"), "<fn>")


if __name__ == "__main__":
    unittest.main()
