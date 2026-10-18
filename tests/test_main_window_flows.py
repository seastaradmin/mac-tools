import unittest
from unittest.mock import patch

from PyQt6.QtWidgets import QDialog, QSystemTrayIcon

from ui.main_window import MainWindow


class FakeTimer:
    def __init__(self):
        self.stopped = False

    def stop(self):
        self.stopped = True


class FakeThread:
    def __init__(self, running):
        self.running = running
        self.quit_called = False

    def isRunning(self):
        return self.running

    def quit(self):
        self.quit_called = True


class MainWindowFlowTests(unittest.TestCase):

    def test_tray_left_click_opens_clipboard_history(self):
        class Window:
            def __init__(self):
                self.clipboard_opened = False
                self.window_shown = False
                self.tool_menu_opened = False
                self._tray_menu = type("Menu", (), {"popup": lambda menu, pos: setattr(self, "tool_menu_opened", True)})()

            def show_clipboard_history(self):
                self.clipboard_opened = True

            def _show_window(self):
                self.window_shown = True

            def _menu_position(self, *_args):
                return None

        window = Window()

        MainWindow._on_tray_activated(window, QSystemTrayIcon.ActivationReason.Trigger)

        self.assertTrue(window.clipboard_opened)
        self.assertFalse(window.window_shown)
        self.assertFalse(window.tool_menu_opened)

    def test_tray_context_click_opens_tool_menu_only(self):
        class Window:
            def __init__(self):
                self.clipboard_opened = False
                self.tool_menu_opened = False
                self._tray_menu = type("Menu", (), {"popup": lambda menu, pos: setattr(self, "tool_menu_opened", True)})()

            def show_clipboard_history(self):
                self.clipboard_opened = True

            def _menu_position(self, *_args):
                return None

        window = Window()

        MainWindow._on_tray_activated(window, QSystemTrayIcon.ActivationReason.Context)

        self.assertFalse(window.clipboard_opened)
        self.assertTrue(window.tool_menu_opened)

    def test_cancelled_screenshot_does_not_restore_when_window_started_hidden(self):
        class Window:
            def __init__(self):
                self._restore_after_screenshot = False
                self.shown = False

            def isVisible(self):
                return False

            def _show_window(self):
                self.shown = True

            def _notify(self, *_args):
                pass

            def _restore_main_after_screenshot(self):
                MainWindow._restore_main_after_screenshot(self)

        window = Window()

        MainWindow._on_screenshot_cancelled(window)

        self.assertFalse(window.shown)
        self.assertFalse(window._restore_after_screenshot)

    def test_cancelled_screenshot_restores_when_window_was_visible(self):
        class Window:
            def __init__(self):
                self._restore_after_screenshot = True
                self.shown = False

            def isVisible(self):
                return False

            def _show_window(self):
                self.shown = True

            def _notify(self, *_args):
                pass

            def _restore_main_after_screenshot(self):
                MainWindow._restore_main_after_screenshot(self)

        window = Window()

        MainWindow._on_screenshot_completed(window, "")

        self.assertTrue(window.shown)
        self.assertFalse(window._restore_after_screenshot)

    def test_screenshot_overlay_not_started_without_screen_recording_permission(self):
        class Overlay:
            def __init__(self):
                self.started = False

            def start(self):
                self.started = True
                return True

        class Window:
            def __init__(self):
                self._restore_after_screenshot = True
                self._screenshot_overlay = Overlay()
                self.errors = []
                self.setup_shown = False
                self.shown = False

            def _notify_error(self, title, message):
                self.errors.append((title, message))

            def _show_screen_recording_setup(self):
                self.setup_shown = True

            def _restore_main_after_screenshot(self):
                MainWindow._restore_main_after_screenshot(self)

            def isVisible(self):
                return False

            def _show_window(self):
                self.shown = True

        window = Window()

        with patch("ui.main_window.is_screen_recording_trusted", return_value=False):
            MainWindow._start_screenshot_overlay(window)

        self.assertFalse(window._screenshot_overlay.started)
        self.assertTrue(window.setup_shown)
        self.assertTrue(window.shown)
        self.assertEqual(window.errors[0][0], "截图失败")

    def test_hotkey_permission_retry_restarts_hotkeys_when_permissions_become_available(self):
        class Hotkeys:
            def __init__(self):
                self.stopped = False
                self.started = False

            def stop(self):
                self.stopped = True

            def start(self):
                self.started = True

        class Tray:
            def __init__(self):
                self.tooltip = None

            def setToolTip(self, value):
                self.tooltip = value

        class Window:
            def __init__(self):
                self.hotkey_manager = Hotkeys()
                self._tray = Tray()
                self._hotkeys_ready_notified = False
                self.notifications = []

            def _notify(self, title, message, *_args, **_kwargs):
                self.notifications.append((title, message))

            def _hotkey_permissions_ready(self):
                return MainWindow._hotkey_permissions_ready(self)

            def _poll_hotkey_permissions_for_hotkeys(self):
                return MainWindow._poll_hotkey_permissions_for_hotkeys(self)

        window = Window()

        with patch("ui.main_window.is_accessibility_trusted", return_value=True), \
             patch("ui.main_window.is_input_monitoring_trusted", return_value=True):
            MainWindow._poll_hotkey_permissions_for_hotkeys(window)

        self.assertTrue(window.hotkey_manager.stopped)
        self.assertTrue(window.hotkey_manager.started)
        self.assertEqual(window._tray.tooltip, "Mac Tools")
        self.assertEqual(window.notifications[0][0], "快捷键已启用")

    def test_hotkey_permission_retry_waits_for_input_monitoring(self):
        class Hotkeys:
            def __init__(self):
                self.stopped = False
                self.started = False

            def stop(self):
                self.stopped = True

            def start(self):
                self.started = True

        class Tray:
            def __init__(self):
                self.tooltip = None

            def setToolTip(self, value):
                self.tooltip = value

        class Window:
            def __init__(self):
                self.hotkey_manager = Hotkeys()
                self._tray = Tray()
                self._hotkeys_ready_notified = False
                self._hotkey_permission_retry_count = 0

            def _notify(self, *_args, **_kwargs):
                raise AssertionError("unexpected notification")

            def _hotkey_permissions_ready(self):
                return MainWindow._hotkey_permissions_ready(self)

            def _poll_hotkey_permissions_for_hotkeys(self):
                return MainWindow._poll_hotkey_permissions_for_hotkeys(self)

        window = Window()

        with patch("ui.main_window.is_accessibility_trusted", return_value=True), \
             patch("ui.main_window.is_input_monitoring_trusted", return_value=False), \
             patch("ui.main_window.QTimer.singleShot") as single_shot:
            MainWindow._poll_hotkey_permissions_for_hotkeys(window)

        self.assertFalse(window.hotkey_manager.stopped)
        self.assertFalse(window.hotkey_manager.started)
        self.assertEqual(window._hotkey_permission_retry_count, 1)
        single_shot.assert_called_once()

    def test_pinned_screenshot_creates_pin_window_and_restores(self):
        class Window:
            def __init__(self):
                self._restore_after_screenshot = True
                self.shown = False
                self.pinned = []
                self.notifications = []

            def _create_pin_window(self, pixmap):
                self.pinned.append(pixmap)

            def _notify(self, title, message, *_args):
                self.notifications.append((title, message))

            def _restore_main_after_screenshot(self):
                MainWindow._restore_main_after_screenshot(self)

            def isVisible(self):
                return False

            def _show_window(self):
                self.shown = True

        window = Window()
        pixmap = object()

        MainWindow._on_screenshot_pin_requested(window, pixmap)

        self.assertEqual(window.pinned, [pixmap])
        self.assertTrue(window.shown)
        self.assertFalse(window._restore_after_screenshot)
        self.assertEqual(window.notifications[0][0], "截图已贴到桌面")

    def test_empty_recording_notifies_without_starting_recognition(self):
        class Window:
            def __init__(self):
                self.is_recording = True
                self._voice_row = type("VoiceRow", (), {"set_active_style": lambda *_args: None})()
                self._record_indicator = type("Indicator", (), {"stop": lambda *_args: None})()
                self._record_timer = FakeTimer()
                self._level_timer = FakeTimer()
                self.recorder = type("Recorder", (), {"stop_recording": lambda _self: None})()
                self.notifications = []
                self.recognized = False
                self._restore_after_recording = False
                self.shown = False

            def _notify(self, title, message, *_args):
                self.notifications.append((title, message))

            def _notify_error(self, *_args):
                raise AssertionError("unexpected error notification")

            def isVisible(self):
                return False

            def _show_window(self):
                self.shown = True

            def _stream_recognize(self, _audio_path):
                self.recognized = True

        window = Window()

        MainWindow._stop_recording(window)

        self.assertFalse(window.is_recording)
        self.assertFalse(window.recognized)
        self.assertEqual(window.notifications[0][0], "录音已取消")
        self.assertTrue(window._record_timer.stopped)
        self.assertTrue(window._level_timer.stopped)

    def test_cancelled_recording_restores_window_when_started_visible(self):
        class Window:
            def __init__(self):
                self.is_recording = True
                self._voice_row = type("VoiceRow", (), {"set_active_style": lambda *_args: None})()
                self._record_indicator = type("Indicator", (), {"stop": lambda *_args: None})()
                self._record_timer = FakeTimer()
                self._level_timer = FakeTimer()
                self.recorder = type("Recorder", (), {"stop_recording": lambda _self: None})()
                self._restore_after_recording = True
                self.shown = False

            def _notify(self, *_args):
                pass

            def isVisible(self):
                return False

            def _show_window(self):
                self.shown = True

            def _stream_recognize(self, _audio_path):
                raise AssertionError("unexpected recognition")

        window = Window()

        MainWindow._stop_recording(window)

        self.assertTrue(window.shown)
        self.assertFalse(window._restore_after_recording)

    def test_start_recording_keeps_main_window_visible(self):
        class Window:
            def __init__(self):
                self._restore_after_recording = False
                self.is_recording = False
                self._voice_row = type("VoiceRow", (), {"set_active_style": lambda *_args: None})()
                self.recorder = type("Recorder", (), {"start_recording": lambda _self: None})()
                self._record_timer = type("Timer", (), {"start": lambda *_args: None})()
                self._level_timer = type("Timer", (), {"start": lambda *_args: None})()
                self._record_indicator = type(
                    "Indicator",
                    (),
                    {
                        "start": lambda *_args: None,
                        "set_time": lambda *_args: None,
                        "set_audio_level": lambda *_args: None,
                    },
                )()
                self._record_seconds = 99
                self.hidden = False

            def isVisible(self):
                return True

            def hide(self):
                self.hidden = True

            def _notify_error(self, *_args):
                raise AssertionError("unexpected error notification")

        window = Window()

        MainWindow._start_recording(window)

        self.assertTrue(window.is_recording)
        self.assertFalse(window.hidden)

    def test_show_settings_pauses_global_hotkeys_while_dialog_is_open(self):
        class Hotkeys:
            def __init__(self):
                self.is_running = True
                self.stopped = False
                self.started = False

            def stop(self):
                self.stopped = True
                self.is_running = False

            def start(self):
                self.started = True
                self.is_running = True

        class Dialog:
            def __init__(self, parent):
                self.parent = parent

            def exec(self):
                self.parent.hotkeys_running_during_dialog = self.parent.hotkey_manager.is_running
                return QDialog.DialogCode.Rejected

        class Window:
            def __init__(self):
                self.hotkey_manager = Hotkeys()
                self.hotkeys_running_during_dialog = True

            def _hotkey_permissions_ready(self):
                return True

        window = Window()

        with patch("ui.main_window.SettingsDialog", Dialog):
            MainWindow.show_settings(window)

        self.assertTrue(window.hotkey_manager.stopped)
        self.assertFalse(window.hotkeys_running_during_dialog)
        self.assertTrue(window.hotkey_manager.started)

    def test_notify_is_suppressed_when_notifications_are_disabled(self):
        class Tray:
            def __init__(self):
                self.calls = []

            def showMessage(self, *args):
                self.calls.append(args)

        class Window:
            def __init__(self):
                self._notifications_enabled = False
                self._tray = Tray()

            def _notify(self, *args, **kwargs):
                return MainWindow._notify(self, *args, **kwargs)

        window = Window()

        MainWindow._notify(window, "标题", "内容")
        MainWindow._notify_error(window, "错误", "内容")

        self.assertEqual(window._tray.calls, [])

    def test_close_event_hides_window_and_keeps_app_running(self):
        class Event:
            def __init__(self):
                self.ignored = False

            def ignore(self):
                self.ignored = True

        class Window:
            def __init__(self):
                self.hidden = False

            def hide(self):
                self.hidden = True

        window = Window()
        event = Event()

        MainWindow.closeEvent(window, event)

        self.assertTrue(event.ignored)
        self.assertTrue(window.hidden)

    def test_clipboard_history_selection_copies_without_auto_paste(self):
        class ClipboardHistory:
            def __init__(self):
                self.copied = []

            def copy_text(self, text):
                self.copied.append(text)
                return True

        class Window:
            def __init__(self):
                self._clipboard_history_auto_paste = False
                self.clipboard_history = ClipboardHistory()
                self.notifications = []

            def _notify(self, title, message, *_args, **_kwargs):
                self.notifications.append((title, message))

            def _notify_error(self, *_args, **_kwargs):
                raise AssertionError("unexpected error notification")

        window = Window()

        MainWindow._use_clipboard_history_text(window, "hello")

        self.assertEqual(window.clipboard_history.copied, ["hello"])
        self.assertEqual(window.notifications[0][0], "已复制剪贴板历史")

    def test_clipboard_history_selection_can_auto_paste(self):
        class Window:
            def __init__(self):
                self._clipboard_history_auto_paste = True
                self.notifications = []

            def _notify(self, title, message, *_args, **_kwargs):
                self.notifications.append((title, message))

            def _notify_error(self, *_args, **_kwargs):
                raise AssertionError("unexpected error notification")

        window = Window()

        with patch("ui.main_window.type_text", return_value="pasted") as paste:
            MainWindow._use_clipboard_history_text(window, "hello")

        paste.assert_called_once_with("hello", target_bundle_id=None)
        self.assertEqual(window.notifications[0][0], "已粘贴剪贴板历史")

    def test_clipboard_history_selection_pastes_to_target_app(self):
        class Window:
            def __init__(self):
                self._clipboard_history_auto_paste = True
                self.notifications = []

            def _notify(self, title, message, *_args, **_kwargs):
                self.notifications.append((title, message))

            def _notify_error(self, *_args, **_kwargs):
                raise AssertionError("unexpected error notification")

        window = Window()

        with patch("ui.main_window.type_text", return_value="pasted") as paste:
            MainWindow._use_clipboard_history_text(window, "hello", target_bundle_id="com.apple.TextEdit")

        paste.assert_called_once_with("hello", target_bundle_id="com.apple.TextEdit")

    def test_voice_paste_uses_recorded_target_app(self):
        class Window:
            def __init__(self):
                self._voice_target_bundle_id = "com.apple.TextEdit"
                self.notifications = []

            def _notify(self, title, message, *_args, **_kwargs):
                self.notifications.append((title, message))

            def _notify_error(self, *_args, **_kwargs):
                raise AssertionError("unexpected error notification")

            def _restore_window_after_paste(self):
                pass

        window = Window()

        with patch("ui.main_window.type_text", return_value="pasted") as paste, \
             patch("ui.main_window.QTimer.singleShot"):
            MainWindow._paste_and_notify(window, "hello")

        paste.assert_called_once_with("hello", target_bundle_id="com.apple.TextEdit")
        self.assertIsNone(window._voice_target_bundle_id)

    def test_stop_recording_keeps_indicator_visible_during_recognition(self):
        class VoiceRow:
            def __init__(self):
                self.active = True

            def set_active_style(self, active):
                self.active = active

        class Indicator:
            def __init__(self):
                self.calls = []

            def show_transcribing(self):
                self.calls.append("transcribing")

            def stop(self):
                self.calls.append("stop")

        class Recorder:
            def stop_recording(self):
                return "/tmp/voice.wav"

        class Window:
            def __init__(self):
                self.is_recording = True
                self._voice_row = VoiceRow()
                self._record_indicator = Indicator()
                self._record_timer = FakeTimer()
                self._level_timer = FakeTimer()
                self.recorder = Recorder()
                self.streamed_path = None

            def _stream_recognize(self, audio_path):
                self.streamed_path = audio_path

        window = Window()

        MainWindow._stop_recording(window)

        self.assertFalse(window.is_recording)
        self.assertFalse(window._voice_row.active)
        self.assertTrue(window._record_timer.stopped)
        self.assertTrue(window._level_timer.stopped)
        self.assertEqual(window._record_indicator.calls, ["transcribing"])
        self.assertEqual(window.streamed_path, "/tmp/voice.wav")

    def test_voice_paste_completion_updates_indicator(self):
        class Indicator:
            def __init__(self):
                self.done = None

            def show_done(self, message):
                self.done = message

        class Window:
            def __init__(self):
                self._voice_target_bundle_id = "com.apple.TextEdit"
                self._record_indicator = Indicator()
                self.notifications = []
                self.restored = False

            def _notify(self, title, message, *_args, **_kwargs):
                self.notifications.append((title, message))

            def _notify_error(self, *_args, **_kwargs):
                raise AssertionError("unexpected error notification")

            def _restore_window_after_paste(self):
                self.restored = True

        window = Window()

        with patch("ui.main_window.type_text", return_value="pasted"):
            with patch("ui.main_window.QTimer.singleShot", lambda _ms, fn: fn()):
                MainWindow._paste_and_notify(window, "hello world")

        self.assertEqual(window._record_indicator.done, "已插入 11 字")
        self.assertTrue(window.restored)

    def test_cleanup_threads_keeps_running_recognition(self):
        running = FakeThread(True)
        finished = FakeThread(False)
        window = type("Window", (), {"_active_threads": [running, finished]})()

        MainWindow._cleanup_threads(window)

        self.assertEqual(window._active_threads, [running])
        self.assertFalse(running.quit_called)
        self.assertTrue(MainWindow._has_running_recognition(window))

    def test_quit_closes_recorder_even_when_idle(self):
        class Recorder:
            def __init__(self):
                self.closed = False

            def close(self):
                self.closed = True

        class Window:
            def __init__(self):
                self._tray = type("Tray", (), {"hide": lambda *_args: None})()
                self.hotkey_manager = type("Hotkeys", (), {"stop": lambda *_args: None})()
                self._record_timer = FakeTimer()
                self._level_timer = FakeTimer()
                self._record_indicator = type("Indicator", (), {"close": lambda *_args: None})()
                self.recorder = Recorder()
                self._active_threads = []
                self.pin_windows = []

        window = Window()

        with patch("ui.main_window.QApplication.quit"):
            MainWindow._quit_app(window)

        self.assertTrue(window.recorder.closed)


if __name__ == "__main__":
    unittest.main()
