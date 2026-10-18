import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app_diagnostics


class AppDiagnosticsTests(unittest.TestCase):

    def test_collect_diagnostics_reports_permissions_and_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            screenshots = root / "screenshots"
            audio = root / "audio"
            screenshots.mkdir()
            audio.mkdir()

            with patch.object(app_diagnostics, "SCREENSHOT_DIR", screenshots), \
                 patch.object(app_diagnostics, "AUDIO_DIR", audio), \
                 patch.object(app_diagnostics, "CONFIG_FILE", root / "config.json"), \
                 patch.object(app_diagnostics, "MIMO_API_KEY", "key"):
                items = dict(app_diagnostics.collect_diagnostics(
                    accessibility_checker=lambda: False,
                    input_monitoring_checker=lambda: False,
                    screen_checker=lambda: True,
                ))

        self.assertEqual(items["辅助功能"], "需要配置")
        self.assertEqual(items["输入监控"], "需要配置")
        self.assertEqual(items["屏幕录制"], "已允许")
        self.assertEqual(items["语音识别 API"], "已配置")
        self.assertIn("可写", items["截图目录"])
        self.assertIn("可写", items["音频缓存"])

    def test_format_diagnostics_report_is_readable(self):
        report = app_diagnostics.format_diagnostics_report([
            ("辅助功能", "需要配置"),
            ("截图目录", "/tmp/screenshots（可写）"),
        ])

        self.assertEqual(report, "辅助功能: 需要配置\n截图目录: /tmp/screenshots（可写）")


if __name__ == "__main__":
    unittest.main()
