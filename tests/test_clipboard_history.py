import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

import clipboard_history.service as service
from clipboard_history.service import ClipboardHistoryService
from clipboard_history.store import ClipboardHistoryStore, preview_text
from ui.clipboard_history_dialog import ClipboardHistoryMenuContent


class ClipboardHistoryStoreTests(unittest.TestCase):
    def test_add_text_ignores_empty_duplicate_and_overlong_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ClipboardHistoryStore(Path(tmp) / "history.json", max_items=3, max_text_length=5)

            self.assertFalse(store.add_text(""))
            self.assertFalse(store.add_text("   "))
            self.assertTrue(store.add_text("one"))
            self.assertTrue(store.add_text("two"))
            self.assertFalse(store.add_text("toolong"))
            self.assertTrue(store.add_text("one"))

            self.assertEqual(store.texts(), ["one", "two"])

    def test_add_text_limits_history_size_and_persists(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "history.json"
            store = ClipboardHistoryStore(path, max_items=2)

            store.add_text("one")
            store.add_text("two")
            store.add_text("three")

            self.assertEqual(store.texts(), ["three", "two"])
            reloaded = ClipboardHistoryStore(path, max_items=2)
            self.assertEqual(reloaded.texts(), ["three", "two"])

    def test_preview_text_compacts_whitespace(self):
        self.assertEqual(preview_text("a\n  b\tc", limit=20), "a b c")
        self.assertEqual(preview_text("abcdef", limit=4), "abc…")


class FakePasteboardData:
    def __init__(self, length):
        self._length = length

    def length(self):
        return self._length


class FakePasteboard:
    def __init__(self, text="hello", length=5, change_count=1, types=None):
        self._text = text
        self._data = FakePasteboardData(length)
        self._change_count = change_count
        self._types = types if types is not None else [service.NSPasteboardTypeString]
        self.string_reads = 0

    def changeCount(self):
        return self._change_count

    def types(self):
        return self._types

    def dataForType_(self, _type):
        return self._data

    def stringForType_(self, _type):
        self.string_reads += 1
        return self._text


class FakeNSPasteboard:
    def __init__(self, pasteboard):
        self.pasteboard = pasteboard

    def generalPasteboard(self):
        return self.pasteboard


class ClipboardHistoryServiceTests(unittest.TestCase):
    def test_macos_reader_skips_unchanged_pasteboard_without_reading_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            pasteboard = FakePasteboard()
            reader = ClipboardHistoryService(ClipboardHistoryStore(Path(tmp) / "history.json"))

            with patch.object(service, "NSPasteboard", FakeNSPasteboard(pasteboard)):
                self.assertEqual(reader._read_macos_pasteboard_text(), "hello")
                self.assertEqual(reader._read_macos_pasteboard_text(), "")

            self.assertEqual(pasteboard.string_reads, 1)

    def test_macos_reader_skips_oversized_data_before_reading_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ClipboardHistoryStore(Path(tmp) / "history.json", max_text_length=5)
            pasteboard = FakePasteboard(text="too large", length=100)
            reader = ClipboardHistoryService(store)

            with patch.object(service, "NSPasteboard", FakeNSPasteboard(pasteboard)):
                self.assertEqual(reader._read_macos_pasteboard_text(), "")

            self.assertEqual(pasteboard.string_reads, 0)


class ClipboardHistoryMenuContentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_search_filters_visible_history(self):
        dialog = ClipboardHistoryMenuContent(["alpha note", "beta memo"])

        dialog.search_input.setText("memo")

        self.assertEqual(dialog.list_widget.count(), 1)
        self.assertEqual(dialog.list_widget.item(0).data(Qt.ItemDataRole.UserRole), "beta memo")
        self.assertTrue(dialog.empty_label.isHidden())

    def test_search_shows_empty_state_when_no_match(self):
        dialog = ClipboardHistoryMenuContent(["alpha note"])

        dialog.search_input.setText("missing")

        self.assertEqual(dialog.list_widget.count(), 0)
        self.assertTrue(dialog.list_widget.isHidden())

    def test_hover_selects_item_and_updates_preview(self):
        dialog = ClipboardHistoryMenuContent(["alpha note", "beta memo"])

        item = dialog.list_widget.item(1)
        dialog._show_preview_for_item(item)

        self.assertEqual(dialog.list_widget.currentItem(), item)
        self.assertIn("beta memo", dialog.preview_label.text())

    def test_hover_item_at_selects_item_under_pointer(self):
        dialog = ClipboardHistoryMenuContent(["alpha note", "beta memo"])
        item = dialog.list_widget.item(1)

        dialog._hover_item_at(dialog.list_widget.visualItemRect(item).center())

        self.assertEqual(dialog.list_widget.currentItem(), item)


if __name__ == "__main__":
    unittest.main()
