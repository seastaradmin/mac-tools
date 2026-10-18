import unittest
from contextlib import redirect_stdout
from io import StringIO
from unittest.mock import Mock, patch

from voice_input import copy_to_clipboard, type_text


class VoiceInputTests(unittest.TestCase):

    def test_copy_to_clipboard_returns_false_for_empty_text(self):
        self.assertFalse(copy_to_clipboard(""))

    def test_type_text_returns_pasted_when_quartz_succeeds(self):
        proc = Mock()
        proc.communicate.return_value = None
        proc.returncode = 0

        with patch("voice_input.subprocess.Popen", return_value=proc), \
             patch("voice_input._paste_with_quartz", return_value=True), \
             patch("voice_input._paste_with_osascript", return_value=False):
            with redirect_stdout(StringIO()):
                self.assertEqual(type_text("hello"), "pasted")

    def test_type_text_returns_copied_when_paste_fails(self):
        proc = Mock()
        proc.communicate.return_value = None
        proc.returncode = 0

        with patch("voice_input.subprocess.Popen", return_value=proc), \
             patch("voice_input._paste_with_quartz", return_value=False), \
             patch("voice_input._paste_with_osascript", return_value=False):
            with redirect_stdout(StringIO()):
                self.assertEqual(type_text("hello"), "copied")

    def test_type_text_returns_failed_when_copy_fails(self):
        proc = Mock()
        proc.communicate.return_value = None
        proc.returncode = 1

        with patch("voice_input.subprocess.Popen", return_value=proc), \
             patch("voice_input._paste_with_quartz") as paste:
            with redirect_stdout(StringIO()):
                self.assertEqual(type_text("hello"), "failed")
        paste.assert_not_called()

    def test_type_text_activates_target_before_paste(self):
        proc = Mock()
        proc.communicate.return_value = None
        proc.returncode = 0

        with patch("voice_input.subprocess.Popen", return_value=proc), \
             patch("voice_input._activate_target_app") as activate, \
             patch("voice_input._paste_with_quartz", return_value=True), \
             patch("voice_input._paste_with_osascript", return_value=False):
            with redirect_stdout(StringIO()):
                self.assertEqual(type_text("hello", target_bundle_id="com.apple.TextEdit"), "pasted")
        activate.assert_called_once_with("com.apple.TextEdit")


if __name__ == "__main__":
    unittest.main()
