"""
设置对话框 - 极简设计，含快捷键配置
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QFrame,
    QCheckBox, QDialogButtonBox, QApplication, QGraphicsDropShadowEffect
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QKeyEvent, QColor

from ui.styles import (
    COLORS, SIZES, primary_button_style,
    ghost_button_style, hotkey_badge_style
)
from config import load_user_config, save_user_config, DEFAULT_HOTKEYS


def _add_shadow(widget, blur=20, opacity=0.05, y_offset=1):
    shadow = QGraphicsDropShadowEffect(widget)
    shadow.setBlurRadius(blur)
    shadow.setColor(QColor(0, 0, 0, int(255 * opacity)))
    shadow.setOffset(0, y_offset)
    widget.setGraphicsEffect(shadow)
    return shadow


# ═══════════════════════════════════════════════════════════
#  快捷键录制徽章
# ═══════════════════════════════════════════════════════════

class HotkeyBadge(QFrame):
    """可点击录制快捷键的徽章组件"""

    hotkey_changed = pyqtSignal(str)  # 新快捷键
    MAC_NATIVE_SHIFT = 1 << 17
    MAC_NATIVE_CONTROL = 1 << 18
    MAC_NATIVE_ALT = 1 << 19
    MAC_NATIVE_COMMAND = 1 << 20
    MAC_NATIVE_FN = 1 << 23
    MODIFIER_KEYS = {
        Qt.Key.Key_Shift,
        Qt.Key.Key_Control,
        Qt.Key.Key_Meta,
        Qt.Key.Key_Alt,
        Qt.Key.Key_AltGr,
    }

    def __init__(self, action: str, current_key: str, parent=None):
        super().__init__(parent)
        self._action = action
        self._key = current_key
        self._recording = False
        self._pressed_keys = set()
        self._modifier_keys = set()
        self._last_modifier_parts = []

        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setFixedHeight(36)
        self.setMinimumWidth(120)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 12, 0)
        layout.setSpacing(0)

        self._label = QLabel(self._format_display(current_key))
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setStyleSheet("background: transparent; border: none;")
        layout.addWidget(self._label)

        self._apply_style()

    def _format_display(self, key_str: str) -> str:
        """将快捷键字符串格式化为显示文本"""
        parts = key_str.replace("<", "").replace(">", "").split("+")
        symbols = {
            "cmd": "⌘", "shift": "⇧", "ctrl": "⌃", "alt": "⌥", "fn": "fn",
        }
        display_parts = []
        for p in parts:
            p_lower = p.lower().strip()
            display_parts.append(symbols.get(p_lower, p.upper()))
        return " ".join(display_parts)

    def _apply_style(self):
        if self._recording:
            self.setStyleSheet(f"""
                QFrame {{
                    background-color: {COLORS['accent_soft']};
                    border: 2px solid {COLORS['accent']};
                    border-radius: 8px;
                }}
            """)
            self._label.setStyleSheet(f"""
                color: {COLORS['accent']};
                font-size: 13px;
                font-weight: 600;
                background: transparent;
                border: none;
            """)
        else:
            self.setStyleSheet(f"""
                QFrame {{
                    background-color: {COLORS['bg_input']};
                    border: none;
                    border-radius: 8px;
                }}
                QFrame:hover {{
                    background-color: {COLORS['bg_hover']};
                }}
            """)
            self._label.setStyleSheet(f"""
                color: {COLORS['text_primary']};
                font-size: 13px;
                font-weight: 600;
                font-family: "SF Mono", "Menlo", monospace;
                background: transparent;
                border: none;
            """)

    def mousePressEvent(self, event):
        if self._recording:
            self._stop_recording()
        else:
            self._start_recording()

    def _start_recording(self):
        self._recording = True
        self._pressed_keys.clear()
        self._modifier_keys.clear()
        self._last_modifier_parts = []
        self._label.setText("按下新快捷键…")
        self._apply_style()
        self.setFocus()

    def _stop_recording(self):
        self._recording = False
        self._last_modifier_parts = []
        self._label.setText(self._format_display(self._key))
        self._apply_style()
        self.clearFocus()

    def _commit_hotkey(self, full_key: str):
        self._key = full_key
        self.hotkey_changed.emit(full_key)
        self._stop_recording()

    def _native_modifiers(self, event: QKeyEvent) -> int:
        try:
            return int(event.nativeModifiers())
        except Exception:
            return 0

    def _modifier_parts(self, event: QKeyEvent) -> list[str]:
        native = self._native_modifiers(event)
        if native:
            parts = []
            if native & self.MAC_NATIVE_COMMAND:
                parts.append("<cmd>")
            if native & self.MAC_NATIVE_SHIFT:
                parts.append("<shift>")
            if native & self.MAC_NATIVE_CONTROL:
                parts.append("<ctrl>")
            if native & self.MAC_NATIVE_ALT:
                parts.append("<alt>")
            if native & self.MAC_NATIVE_FN:
                parts.append("<fn>")
            return parts

        mod = event.modifiers()
        parts = []
        if mod & Qt.KeyboardModifier.MetaModifier:
            parts.append("<cmd>")
        if mod & Qt.KeyboardModifier.ShiftModifier:
            parts.append("<shift>")
        if mod & Qt.KeyboardModifier.ControlModifier:
            parts.append("<ctrl>")
        if mod & Qt.KeyboardModifier.AltModifier:
            parts.append("<alt>")
        return parts

    def _display_parts(self, modifier_parts: list[str]) -> list[str]:
        symbols = {"<cmd>": "⌘", "<shift>": "⇧", "<ctrl>": "⌃", "<alt>": "⌥", "<fn>": "fn"}
        return [symbols[p] for p in modifier_parts if p in symbols]

    def keyPressEvent(self, event: QKeyEvent):
        if not self._recording:
            return

        key = event.key()
        mod_parts = self._modifier_parts(event)
        if mod_parts:
            self._last_modifier_parts = mod_parts

        # 按 Esc 取消
        if key == Qt.Key.Key_Escape:
            self._stop_recording()
            return

        # 如果有非修饰键按下，组合成快捷键
        if key not in self.MODIFIER_KEYS:
            key_char = self._qt_key_to_char(key)
            if key_char:
                full_key = "+".join(mod_parts + [key_char])
                self._commit_hotkey(full_key)
                return

        # 仅修饰键时显示当前按下的修饰键
        display_parts = self._display_parts(mod_parts)
        if display_parts:
            self._label.setText(" ".join(display_parts) + " …")

    def keyReleaseEvent(self, event: QKeyEvent):
        if not self._recording:
            return
        if self._last_modifier_parts == ["<fn>"]:
            self._commit_hotkey("<fn>")

    def focusOutEvent(self, event):
        if self._recording:
            self._stop_recording()
        super().focusOutEvent(event)

    def _qt_key_to_char(self, key) -> str:
        """将 Qt 按键转换为字符"""
        if Qt.Key.Key_A <= key <= Qt.Key.Key_Z:
            return chr(key).lower()
        if Qt.Key.Key_0 <= key <= Qt.Key.Key_9:
            return chr(key)
        special = {
            Qt.Key.Key_Space: "space",
            Qt.Key.Key_Return: "return",
            Qt.Key.Key_Enter: "enter",
            Qt.Key.Key_Tab: "tab",
            Qt.Key.Key_Backspace: "backspace",
            Qt.Key.Key_Delete: "delete",
            Qt.Key.Key_Escape: "esc",
            Qt.Key.Key_F1: "f1", Qt.Key.Key_F2: "f2", Qt.Key.Key_F3: "f3",
            Qt.Key.Key_F4: "f4", Qt.Key.Key_F5: "f5", Qt.Key.Key_F6: "f6",
            Qt.Key.Key_F7: "f7", Qt.Key.Key_F8: "f8", Qt.Key.Key_F9: "f9",
            Qt.Key.Key_F10: "f10", Qt.Key.Key_F11: "f11", Qt.Key.Key_F12: "f12",
        }
        return special.get(key, None)

    def get_key(self) -> str:
        return self._key


# ═══════════════════════════════════════════════════════════
#  设置对话框
# ═══════════════════════════════════════════════════════════

class SettingsDialog(QDialog):
    """设置对话框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.setFixedWidth(440)
        self.setMinimumHeight(360)

        self.config = load_user_config()
        self._hotkey_badges = {}

        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 20)
        layout.setSpacing(24)

        # ── 快捷键 ───────────────────────────────────
        section_hotkey = self._section_title("快捷键")
        layout.addWidget(section_hotkey)

        hotkey_card = QFrame()
        hotkey_card.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['bg_card']};
                border-radius: {SIZES['radius_lg']};
                border: none;
            }}
        """)
        _add_shadow(hotkey_card)
        hk_layout = QVBoxLayout(hotkey_card)
        hk_layout.setContentsMargins(16, 14, 16, 14)
        hk_layout.setSpacing(12)

        hotkey_items = [
            ("screenshot", "截图", self.config.get("hotkey_screenshot", DEFAULT_HOTKEYS.get("screenshot", "<cmd>+<shift>+s"))),
            ("voice_input", "语音输入", self.config.get("hotkey_voice_input", DEFAULT_HOTKEYS.get("voice_input", "<cmd>+<shift>+v"))),
            ("clipboard_history", "剪贴板历史", self.config.get("hotkey_clipboard_history", DEFAULT_HOTKEYS.get("clipboard_history", "<cmd>+<shift>+h"))),
        ]

        for action, label, key in hotkey_items:
            row = QFrame()
            row.setStyleSheet("QFrame { background: transparent; border: none; }")
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(4, 0, 4, 0)

            icon_map = {"screenshot": "📷", "voice_input": "🎙", "clipboard_history": "📋"}
            icon_lbl = QLabel(icon_map.get(action, "⌘"))
            icon_lbl.setFixedSize(32, 32)
            icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            icon_lbl.setStyleSheet(f"""
                background-color: {COLORS['bg_input']};
                border-radius: {SIZES['radius_sm']};
                font-size: 14px;
                color: {COLORS['text_secondary']};
            """)
            row_layout.addWidget(icon_lbl)

            name_lbl = QLabel(label)
            name_lbl.setStyleSheet(f"""
                font-size: 14px;
                font-weight: 500;
                color: {COLORS['text_primary']};
            """)
            row_layout.addWidget(name_lbl, 1)

            badge = HotkeyBadge(action, key)
            badge.hotkey_changed.connect(lambda new_key, a=action: self._on_hotkey_changed(a, new_key))
            self._hotkey_badges[action] = badge
            row_layout.addWidget(badge)

            hk_layout.addWidget(row)

        # 提示
        hint = QLabel("点击快捷键徽章可重新录制")
        hint.setStyleSheet(f"""
            font-size: 12px;
            color: {COLORS['text_hint']};
            padding-left: 4px;
        """)
        hk_layout.addWidget(hint)

        layout.addWidget(hotkey_card)

        # ── API 配置 ─────────────────────────────────
        section_api = self._section_title("语音识别")
        layout.addWidget(section_api)

        api_card = QFrame()
        api_card.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['bg_card']};
                border-radius: {SIZES['radius_lg']};
                border: none;
            }}
        """)
        _add_shadow(api_card)
        api_layout = QVBoxLayout(api_card)
        api_layout.setContentsMargins(16, 14, 16, 14)
        api_layout.setSpacing(10)

        # API Key 行
        key_row = QHBoxLayout()
        self.api_key_input = QLineEdit()
        self.api_key_input.setPlaceholderText("MiMo API Key")
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        current_key = self.config.get("mimo_api_key", "")
        if current_key:
            self.api_key_input.setText(current_key)
        key_row.addWidget(self.api_key_input, 1)

        self.show_key_btn = QPushButton("显示")
        self.show_key_btn.setStyleSheet(ghost_button_style("sm"))
        self.show_key_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.show_key_btn.clicked.connect(self._toggle_key_visibility)
        key_row.addWidget(self.show_key_btn)

        api_layout.addLayout(key_row)

        # 获取链接
        link = QLabel('获取 Key: <a href="https://platform.xiaomimimo.com/" style="color: {c}; text-decoration: none;">小米 MiMo 开放平台</a>'.format(c=COLORS['accent']))
        link.setOpenExternalLinks(True)
        link.setStyleSheet(f"font-size: 12px; color: {COLORS['text_hint']};")
        api_layout.addWidget(link)

        layout.addWidget(api_card)

        # ── 通知 ─────────────────────────────────
        notify_card = QFrame()
        notify_card.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['bg_card']};
                border-radius: {SIZES['radius_lg']};
                border: none;
            }}
        """)
        _add_shadow(notify_card)
        notify_layout = QHBoxLayout(notify_card)
        notify_layout.setContentsMargins(16, 12, 16, 12)

        self.notifications_checkbox = QCheckBox("显示系统通知")
        self.notifications_checkbox.setChecked(self.config.get("show_notifications", True))
        self.notifications_checkbox.setStyleSheet(f"""
            QCheckBox {{
                font-size: 13px;
                color: {COLORS['text_primary']};
                spacing: 8px;
            }}
        """)
        notify_layout.addWidget(self.notifications_checkbox)

        layout.addWidget(notify_card)

        clipboard_card = QFrame()
        clipboard_card.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['bg_card']};
                border-radius: {SIZES['radius_lg']};
                border: none;
            }}
        """)
        _add_shadow(clipboard_card)
        clipboard_layout = QVBoxLayout(clipboard_card)
        clipboard_layout.setContentsMargins(16, 12, 16, 12)
        clipboard_layout.setSpacing(10)

        self.clipboard_history_checkbox = QCheckBox("启用剪贴板历史")
        self.clipboard_history_checkbox.setChecked(self.config.get("clipboard_history_enabled", False))
        self.clipboard_history_checkbox.setStyleSheet(self.notifications_checkbox.styleSheet())
        clipboard_layout.addWidget(self.clipboard_history_checkbox)

        self.clipboard_auto_paste_checkbox = QCheckBox("选择历史后自动粘贴")
        self.clipboard_auto_paste_checkbox.setChecked(self.config.get("clipboard_history_auto_paste", False))
        self.clipboard_auto_paste_checkbox.setStyleSheet(self.notifications_checkbox.styleSheet())
        clipboard_layout.addWidget(self.clipboard_auto_paste_checkbox)

        layout.addWidget(clipboard_card)

        # ── 底部按钮 ─────────────────────────────────
        layout.addStretch()

        btn_row = QHBoxLayout()
        btn_row.addStretch()

        cancel_btn = QPushButton("取消")
        cancel_btn.setStyleSheet(ghost_button_style("md"))
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        save_btn = QPushButton("保存")
        save_btn.setStyleSheet(primary_button_style("md"))
        save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_btn.clicked.connect(self._save)
        btn_row.addWidget(save_btn)

        layout.addLayout(btn_row)

    def _section_title(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(f"""
            font-size: 12px;
            font-weight: 600;
            color: {COLORS['text_hint']};
            letter-spacing: 0.5px;
            text-transform: uppercase;
            padding-left: 2px;
        """)
        return lbl

    def _toggle_key_visibility(self):
        if self.api_key_input.echoMode() == QLineEdit.EchoMode.Password:
            self.api_key_input.setEchoMode(QLineEdit.EchoMode.Normal)
            self.show_key_btn.setText("隐藏")
        else:
            self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
            self.show_key_btn.setText("显示")

    def _on_hotkey_changed(self, action: str, new_key: str):
        """快捷键变更回调"""
        pass  # badge 已内部更新，保存时读取

    def _save(self):
        """保存设置"""
        self.config["mimo_api_key"] = self.api_key_input.text().strip()
        self.config["show_notifications"] = self.notifications_checkbox.isChecked()
        self.config["clipboard_history_enabled"] = self.clipboard_history_checkbox.isChecked()
        self.config["clipboard_history_auto_paste"] = self.clipboard_auto_paste_checkbox.isChecked()

        # 保存快捷键
        for action, badge in self._hotkey_badges.items():
            self.config[f"hotkey_{action}"] = badge.get_key()

        if save_user_config(self.config):
            self.accept()
        else:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "错误", "保存设置失败")

    def get_hotkeys(self) -> dict:
        """获取对话框中的快捷键配置"""
        result = {}
        for action, badge in self._hotkey_badges.items():
            result[action] = badge.get_key()
        return result
