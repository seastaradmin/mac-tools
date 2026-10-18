import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from screenshot.capture import ScreenCapture, ScreenCaptureError


class ScreenCaptureTests(unittest.TestCase):

    def test_generate_filename_recreates_missing_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            screenshot_dir = Path(tmp) / "screenshots"
            capture = ScreenCapture()
            capture.screenshot_dir = screenshot_dir

            path = Path(capture._generate_filename("test"))

            self.assertTrue(screenshot_dir.exists())
            self.assertEqual(path.parent, screenshot_dir)
            self.assertTrue(path.name.startswith("test_"))
            self.assertEqual(path.suffix, ".png")

    @patch("screenshot.capture.subprocess.run")
    def test_interactive_cancel_returns_none_without_error(self, run):
        with tempfile.TemporaryDirectory() as tmp:
            output = str(Path(tmp) / "cancelled.png")
            run.return_value = type("Result", (), {"returncode": 0, "stdout": "", "stderr": ""})()

            capture = ScreenCapture()

            self.assertIsNone(capture.capture_interactive(output))

    @patch("screenshot.capture.subprocess.run")
    def test_interactive_failure_raises_stderr(self, run):
        with tempfile.TemporaryDirectory() as tmp:
            output = str(Path(tmp) / "failed.png")
            run.return_value = type(
                "Result",
                (),
                {"returncode": 1, "stdout": "", "stderr": "screen capture denied"},
            )()

            capture = ScreenCapture()

            with self.assertRaisesRegex(ScreenCaptureError, "screen capture denied"):
                capture.capture_interactive(output)


if __name__ == "__main__":
    unittest.main()
