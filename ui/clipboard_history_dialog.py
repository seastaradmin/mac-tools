from PyQt6.QtCore import QEvent, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QPushButton, QVBoxLayout, QWidget
)

from clipboard_history.store import preview_text
from ui.styles import COLORS, GLOBAL_STYLESHEET


class ClipboardHistoryMenuContent(QWidget):
    text_selected = pyqtSignal(str)
    clear_requested = pyqtSignal()
    settings_requested = pyqtSignal()
    show_window_requested = pyqtSignal()
    quit_requested = pyqtSignal()

    def __init__(self, texts: list[str], parent=None):
        super().__init__(parent)
        self._texts = list(texts)
        self.setFixedWidth(320)
        self.setFixedHeight(self._preferred_height(len(texts)))
        self.setStyleSheet(GLOBAL_STYLESHEET + f"""
            QWidget {{
                background-color: {COLORS['bg']};
            }}
            QLineEdit {{
                background-color: rgba(142,142,147,0.12);
                border: none;
                border-radius: 7px;
                padding: 6px 9px;
                font-size: 13px;
            }}
            QListWidget {{
                background-color: {COLORS['bg']};
                border: none;
                outline: none;
                font-size: 13px;
            }}
            QListWidget::item {{
                min-height: 32px;
                padding: 5px 8px;
                border-radius: 7px;
            }}
            QListWidget::item:hover {{
                background-color: rgba(0,122,255,0.10);
            }}
            QListWidget::item:selected {{
                background-color: {COLORS['accent']};
                color: white;
            }}
            QPushButton {{
                background: transparent;
                border: none;
                border-radius: 5px;
                color: {COLORS['text_primary']};
                font-size: 13px;
                padding: 4px 8px;
                text-align: left;
            }}
            QPushButton:hover {{
                background-color: rgba(0,122,255,0.1);
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 7, 8, 7)
        layout.setSpacing(5)

        header = QHBoxLayout()
        title = QLabel("剪贴板历史")
        title.setFixedWidth(72)
        title.setStyleSheet(f"font-size: 13px; color: {COLORS['text_secondary']};")
        header.addWidget(title)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("搜索...")
        self.search_input.textChanged.connect(self._apply_filter)
        header.addWidget(self.search_input, 1)
        layout.addLayout(header)

        self.list_widget = QListWidget()
        self.list_widget.setMouseTracking(True)
        self.list_widget.viewport().setMouseTracking(True)
        self.list_widget.viewport().installEventFilter(self)
        self.list_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list_widget.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.list_widget.itemClicked.connect(self._select_item)
        self.list_widget.itemEntered.connect(self._show_preview_for_item)
        layout.addWidget(self.list_widget, 1)

        self.empty_label = QLabel("暂无文本记录")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setStyleSheet(f"color: {COLORS['text_hint']}; font-size: 13px;")
        layout.addWidget(self.empty_label, 1)

        self.preview_label = QLabel()
        self.preview_label.setWordWrap(True)
        self.preview_label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self.preview_label.setFixedHeight(58)
        self.preview_label.setStyleSheet(f"""
            QLabel {{
                background-color: rgba(142,142,147,0.10);
                color: {COLORS['text_secondary']};
                border-radius: 7px;
                padding: 7px 9px;
                font-size: 12px;
                line-height: 1.25;
            }}
        """)
        layout.addWidget(self.preview_label)

        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setStyleSheet(f"background-color: {COLORS['divider']}; max-height: 1px;")
        layout.addWidget(divider)

        footer = QVBoxLayout()
        footer.setContentsMargins(2, 0, 2, 0)
        footer.setSpacing(0)
        self.clear_button = self._footer_button("清除", self._clear)
        self.settings_button = self._footer_button("偏好设置...", self.settings_requested.emit)
        self.show_window_button = self._footer_button("显示主界面", self.show_window_requested.emit)
        self.quit_button = self._footer_button("退出", self.quit_requested.emit)
        footer.addWidget(self.clear_button)
        footer.addWidget(self.settings_button)
        footer.addWidget(self.show_window_button)
        footer.addWidget(self.quit_button)
        layout.addLayout(footer)

        self.set_texts(texts)
        self.search_input.setFocus()

    @staticmethod
    def _preferred_height(item_count: int) -> int:
        visible_rows = min(max(item_count, 1), 7)
        return min(430, 178 + visible_rows * 42)

    def _footer_button(self, text: str, callback):
        button = QPushButton(text)
        button.clicked.connect(callback)
        return button

    def set_texts(self, texts: list[str]):
        self._texts = list(texts)
        self._hide_preview()
        self._apply_filter(self.search_input.text() if hasattr(self, "search_input") else "")

    def _apply_filter(self, query: str):
        self.list_widget.clear()
        normalized_query = query.strip().lower()
        visible_texts = [
            text for text in self._texts
            if not normalized_query or normalized_query in text.lower()
        ]
        for index, text in enumerate(visible_texts[:50], start=1):
            shortcut = f"    ⌘ {index}" if index < 10 else ""
            item = QListWidgetItem(f"{preview_text(text, 42)}{shortcut}")
            item.setData(Qt.ItemDataRole.UserRole, text)
            self.list_widget.addItem(item)
        has_items = bool(visible_texts)
        self.list_widget.setVisible(has_items)
        self.empty_label.setVisible(not has_items)
        self.preview_label.setVisible(has_items)
        if has_items:
            self.list_widget.setCurrentRow(0)
            self._show_preview_for_item(self.list_widget.item(0))
        else:
            self._hide_preview()

    def _select_item(self, item: QListWidgetItem):
        self._hide_preview()
        text = item.data(Qt.ItemDataRole.UserRole)
        if text:
            self.text_selected.emit(text)

    def _clear(self):
        self._hide_preview()
        self.clear_requested.emit()
        self.set_texts([])

    def _show_preview_for_item(self, item: QListWidgetItem):
        if not item:
            self._hide_preview()
            return
        self.list_widget.setCurrentItem(item)
        text = item.data(Qt.ItemDataRole.UserRole)
        if not text:
            self._hide_preview()
            return
        self.preview_label.setText((text or "").strip()[:260])
        self.preview_label.show()

    def _hover_item_at(self, position):
        item = self.list_widget.itemAt(position)
        if item:
            self._show_preview_for_item(item)
        else:
            self._hide_preview()
        return item

    def _hide_preview(self):
        if hasattr(self, "preview_label"):
            self.preview_label.clear()
            self.preview_label.hide()

    def eventFilter(self, source, event):
        if source is self.list_widget.viewport():
            if event.type() == QEvent.Type.MouseMove:
                self._hover_item_at(event.position().toPoint())
            elif event.type() in (QEvent.Type.Leave, QEvent.Type.Hide):
                self._hide_preview()
        return super().eventFilter(source, event)

    def hideEvent(self, event):
        self._hide_preview()
        super().hideEvent(event)

    def closeEvent(self, event):
        self._hide_preview()
        super().closeEvent(event)
