from PyQt6.QtCore import QObject, QTimer, pyqtSignal
from PyQt6.QtWidgets import QApplication

from clipboard_history.store import ClipboardHistoryStore

try:
    from AppKit import NSPasteboard, NSPasteboardTypeString
except Exception:  # pragma: no cover - non-macOS fallback
    NSPasteboard = None
    NSPasteboardTypeString = "public.utf8-plain-text"


MAX_CLIPBOARD_BYTES_FACTOR = 4


class ClipboardHistoryService(QObject):
    changed = pyqtSignal()

    def __init__(self, store: ClipboardHistoryStore, parent=None, interval_ms: int = 1200):
        super().__init__(parent)
        self.store = store
        self._enabled = False
        self._ignore_next_text = None
        self._last_change_count = None
        self._timer = QTimer(self)
        self._timer.setInterval(interval_ms)
        self._timer.timeout.connect(self.poll)

    def set_enabled(self, enabled: bool):
        self._enabled = bool(enabled)
        if self._enabled:
            self._timer.start()
            self.poll()
        else:
            self._timer.stop()

    def is_enabled(self) -> bool:
        return self._enabled

    def poll(self):
        if not self._enabled:
            return
        text = self._read_current_text()
        if not text:
            return
        if text == self._ignore_next_text:
            self._ignore_next_text = None
            return
        if self.store.add_text(text):
            self.changed.emit()

    def _read_current_text(self):
        text = self._read_macos_pasteboard_text()
        if text is not None:
            return text
        clipboard = QApplication.clipboard()
        if clipboard is None:
            return None
        mime = clipboard.mimeData()
        if mime and (mime.hasImage() or mime.hasUrls()):
            return None
        text = clipboard.text()
        if not self.store.is_valid_text(text):
            return None
        return text

    def _read_macos_pasteboard_text(self):
        if NSPasteboard is None:
            return None
        try:
            pasteboard = NSPasteboard.generalPasteboard()
            change_count = int(pasteboard.changeCount())
            if self._last_change_count == change_count:
                return ""
            self._last_change_count = change_count

            types = list(pasteboard.types() or [])
            if NSPasteboardTypeString not in types:
                return ""

            data = pasteboard.dataForType_(NSPasteboardTypeString)
            if data is None:
                return ""
            max_bytes = self.store.max_text_length * MAX_CLIPBOARD_BYTES_FACTOR
            if int(data.length()) > max_bytes:
                return ""

            text = pasteboard.stringForType_(NSPasteboardTypeString)
            if not self.store.is_valid_text(text):
                return ""
            return str(text)
        except Exception:
            return None

    def copy_text(self, text: str):
        clipboard = QApplication.clipboard()
        if clipboard is None:
            return False
        self._ignore_next_text = text
        clipboard.setText(text)
        return True

    def clear(self):
        self.store.clear()
        self.changed.emit()
