import unittest
from unittest.mock import patch

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

import ui.settings_dialog as settings_dialog
from ui.settings_dialog import HotkeyBadge, SettingsDialog


class FakeKeyEvent:
    def __init__(self, key, modifiers=Qt.KeyboardModifier.NoModifier, native_modifiers=0):
        self._key = key
        self._modifiers = modifiers
        self._native_modifiers = native_modifiers

    def key(self):
        return self._key

    def modifiers(self):
        return self._modifiers

    def nativeModifiers(self):
        return self._native_modifiers


class HotkeyBadgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_native_command_modifier_wins_over_qt_control_modifier_on_macos(self):
        badge = HotkeyBadge("screenshot", "<cmd>+<shift>+s")
        changed = []
        badge.hotkey_changed.connect(changed.append)
        badge._start_recording()

        badge.keyPressEvent(FakeKeyEvent(
            Qt.Key.Key_A,
            modifiers=Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier,
            native_modifiers=(1 << 20) | (1 << 17),
        ))

        self.assertEqual(badge.get_key(), "<cmd>+<shift>+a")
        self.assertEqual(changed, ["<cmd>+<shift>+a"])
        self.assertFalse(badge._recording)

    def test_fn_only_hotkey_commits_on_release(self):
        badge = HotkeyBadge("voice_input", "<fn>")
        changed = []
        badge.hotkey_changed.connect(changed.append)
        badge._start_recording()

        badge.keyPressEvent(FakeKeyEvent(
            Qt.Key.Key_Meta,
            modifiers=Qt.KeyboardModifier.MetaModifier,
            native_modifiers=(1 << 23),
        ))
        badge.keyReleaseEvent(FakeKeyEvent(
            Qt.Key.Key_Meta,
            modifiers=Qt.KeyboardModifier.NoModifier,
            native_modifiers=0,
        ))

        self.assertEqual(badge.get_key(), "<fn>")
        self.assertEqual(changed, ["<fn>"])
        self.assertFalse(badge._recording)


class SettingsDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_save_persists_notification_preference(self):
        saved = []

        with patch.object(settings_dialog, "load_user_config", return_value={
            "hotkey_screenshot": "<cmd>+<shift>+a",
            "hotkey_voice_input": "<fn>",
            "hotkey_clipboard_history": "<cmd>+<shift>+h",
            "show_notifications": True,
            "clipboard_history_enabled": True,
            "clipboard_history_auto_paste": True,
        }), patch.object(settings_dialog, "save_user_config", side_effect=lambda config: saved.append(dict(config)) or True):
            dialog = SettingsDialog()
            dialog.notifications_checkbox.setChecked(False)
            dialog.clipboard_history_checkbox.setChecked(False)
            dialog.clipboard_auto_paste_checkbox.setChecked(False)
            dialog._save()

        self.assertEqual(saved[0]["show_notifications"], False)
        self.assertEqual(saved[0]["clipboard_history_enabled"], False)
        self.assertEqual(saved[0]["clipboard_history_auto_paste"], False)


if __name__ == "__main__":
    unittest.main()
