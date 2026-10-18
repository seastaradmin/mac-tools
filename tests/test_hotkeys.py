import unittest

from hotkeys.manager import HotkeyManager, MacHotkeyEventTap


class HotkeyManagerTests(unittest.TestCase):

    def test_regular_hotkey_fires_once_until_released(self):
        manager = HotkeyManager()
        calls = []
        manager.register_hotkey(
            "screenshot",
            "<cmd>+<shift>+s",
            lambda: calls.append("screenshot"),
        )

        manager._on_key_press("<cmd>")
        manager._on_key_press("<shift>")
        manager._on_key_press("s")
        manager._on_key_press("s")

        self.assertEqual(calls, ["screenshot"])

        manager._on_key_release("s")
        manager._on_key_press("s")

        self.assertEqual(calls, ["screenshot", "screenshot"])

    def test_hold_hotkey_fires_press_once_and_release_once(self):
        manager = HotkeyManager()
        calls = []
        manager.register_hold_hotkey(
            "voice_input",
            "<cmd>+<shift>+v",
            on_press=lambda: calls.append("press"),
            on_release=lambda: calls.append("release"),
        )

        manager._on_key_press("<cmd>")
        manager._on_key_press("<shift>")
        manager._on_key_press("v")
        manager._on_key_press("v")
        manager._on_key_release("v")

        self.assertEqual(calls, ["press", "release"])

    def test_ctrl_letter_control_char_matches_configured_letter(self):
        manager = HotkeyManager()
        calls = []
        manager.register_hold_hotkey(
            "voice_input",
            "<ctrl>+c",
            on_press=lambda: calls.append("press"),
            on_release=lambda: calls.append("release"),
        )

        manager._on_key_press("<ctrl>")
        manager._on_key_press("\x03")
        manager._on_key_release("\x03")

        self.assertEqual(calls, ["press", "release"])

    def test_fn_hold_hotkey_fires_press_once_and_release_once(self):
        manager = HotkeyManager()
        calls = []
        manager.register_hold_hotkey(
            "voice_input",
            "<fn>",
            on_press=lambda: calls.append("press"),
            on_release=lambda: calls.append("release"),
        )

        manager._on_key_press("<fn>")
        manager._on_key_press("<fn>")
        manager._on_key_release("<fn>")

        self.assertEqual(calls, ["press", "release"])

    def test_fn_hotkey_requires_macos_fn_listener(self):
        manager = HotkeyManager()
        manager.register_hold_hotkey(
            "voice_input",
            "<fn>",
            on_press=lambda: None,
            on_release=lambda: None,
        )

        self.assertTrue(manager._requires_fn_listener())

    def test_updating_away_from_fn_removes_fn_requirement(self):
        manager = HotkeyManager()
        manager.register_hold_hotkey(
            "voice_input",
            "<fn>",
            on_press=lambda: None,
            on_release=lambda: None,
        )

        manager.update_hotkey("voice_input", "<cmd>+<shift>+v")

        self.assertFalse(manager._requires_fn_listener())

    def test_macos_event_tap_maps_screenshot_letter(self):
        self.assertEqual(MacHotkeyEventTap.KEY_CODES[1], "s")

    def test_event_tap_ignores_fn_flag_on_regular_key_events(self):
        pressed = []
        tap = MacHotkeyEventTap(
            on_press=lambda key: pressed.append(key) or False,
            on_release=lambda key: False,
        )
        tap._modifier_masks = {"<fn>": 1, "<cmd>": 2}

        self.assertFalse(tap._sync_modifier_flags(1, sync_fn=False))
        self.assertEqual(pressed, [])

        self.assertFalse(tap._sync_modifier_flags(2, sync_fn=False))
        self.assertEqual(pressed, ["<cmd>"])

    def test_event_tap_accepts_fn_flag_on_modifier_events(self):
        pressed = []
        tap = MacHotkeyEventTap(
            on_press=lambda key: pressed.append(key) or False,
            on_release=lambda key: False,
        )
        tap._modifier_masks = {"<fn>": 1}

        self.assertFalse(tap._sync_modifier_flags(1, sync_fn=True))
        self.assertEqual(pressed, ["<fn>"])


if __name__ == "__main__":
    unittest.main()
