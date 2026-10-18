import unittest
from unittest.mock import patch

import macos_permissions


class MacOSPermissionsTests(unittest.TestCase):

    @patch("macos_permissions.subprocess.run")
    @patch("macos_permissions.sys.platform", "darwin")
    def test_open_privacy_settings_opens_accessibility_pane(self, run):
        self.assertTrue(macos_permissions.open_privacy_settings("accessibility"))

        run.assert_called_once_with(
            [
                "open",
                "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility",
            ],
            check=False,
        )

    @patch("macos_permissions.subprocess.run")
    @patch("macos_permissions.sys.platform", "darwin")
    def test_open_privacy_settings_opens_input_monitoring_pane(self, run):
        self.assertTrue(macos_permissions.open_privacy_settings("input_monitoring"))

        run.assert_called_once_with(
            [
                "open",
                "x-apple.systempreferences:com.apple.preference.security?Privacy_ListenEvent",
            ],
            check=False,
        )

    @patch("macos_permissions.subprocess.run")
    @patch("macos_permissions.sys.platform", "darwin")
    def test_open_privacy_settings_rejects_unknown_permission(self, run):
        self.assertFalse(macos_permissions.open_privacy_settings("unknown"))

        run.assert_not_called()

    @patch("macos_permissions.subprocess.run")
    @patch("macos_permissions.sys.platform", "linux")
    def test_open_privacy_settings_returns_false_off_macos(self, run):
        self.assertFalse(macos_permissions.open_privacy_settings("microphone"))

        run.assert_not_called()

    @patch("macos_permissions.sys.platform", "linux")
    def test_prompt_screen_recording_permission_returns_true_off_macos(self):
        self.assertTrue(macos_permissions.prompt_screen_recording_permission())

    @patch("macos_permissions.sys.platform", "linux")
    def test_input_monitoring_permission_returns_true_off_macos(self):
        self.assertTrue(macos_permissions.is_input_monitoring_trusted())
        self.assertTrue(macos_permissions.prompt_input_monitoring_permission())


if __name__ == "__main__":
    unittest.main()
