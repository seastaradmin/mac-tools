"""
浮动截图编辑器 — 钉钉/微信风格 + macOS 红绿灯
截图精确匹配选区 · 顶部控制按钮 · 按钮反馈动效
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea,
    QFileDialog, QApplication, QPushButton, QLabel,
    QFrame, QSpinBox, QColorDialog, QGraphicsDropShadowEffect,
    QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal, QPoint, QSize, QTimer
from PyQt6.QtGui import QPixmap, QMouseEvent, QColor, QPainter, QPen, QFont

from ui.inline_editor import EditorCanvas
from ui.styles import COLORS, SIZES
from ui.window_levels import keep_window_on_top
from config import EditorTool, EDITOR_DEFAULT_LINE_WIDTH


# ═══════════════════════════════════════════════════════════
#  macOS 红绿灯控制按钮
# ═══════════════════════════════════════════════════════════

class TrafficLights(QWidget):
    """macOS 风格红绿灯按钮组"""

    close_clicked = pyqtSignal()
    minimize_clicked = pyqtSignal()
    maximize_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(56, 20)
        self._hover = False

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # 关闭 (红)
        self._close_btn = self._make_dot("#FF5F57", "#E0443E")
        self._close_btn.clicked.connect(self.close_clicked.emit)
        layout.addWidget(self._close_btn)

        # 最小化 (黄)
        self._min_btn = self._make_dot("#FEBC2E", "#DEA123")
        self._min_btn.clicked.connect(self.minimize_clicked.emit)
        layout.addWidget(self._min_btn)

        # 最大化 (绿)
        self._max_btn = self._make_dot("#28C840", "#1AAB29")
        self._max_btn.clicked.connect(self.maximize_clicked.emit)
        layout.addWidget(self._max_btn)

    def _make_dot(self, color, hover_color):
        btn = QPushButton()
        btn.setFixedSize(12, 12)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {color};
                border: 0.5px solid rgba(0,0,0,0.12);
                border-radius: 6px;
            }}
            QPushButton:hover {{
                background-color: {hover_color};
            }}
            QPushButton:pressed {{
                background-color: {hover_color};
            }}
        """)
        return btn

    def enterEvent(self, event):
        self._hover = True

    def leaveEvent(self, event):
        self._hover = False


# ═══════════════════════════════════════════════════════════
#  紧凑工具栏 — 复制在最右
# ═══════════════════════════════════════════════════════════

class CompactToolbar(QFrame):
    """紧凑浮动工具栏"""

    tool_changed = pyqtSignal(str)
    color_changed = pyqtSignal(QColor)
    width_changed = pyqtSignal(int)
    undo_requested = pyqtSignal()
    redo_requested = pyqtSignal()
    save_requested = pyqtSignal()
    copy_requested = pyqtSignal()
    pin_requested = pyqtSignal()
    close_requested = pyqtSignal()

    TOOLS = [
        (EditorTool.PEN, "画笔"),
        (EditorTool.RECTANGLE, "矩形"),
        (EditorTool.CIRCLE, "圆形"),
        (EditorTool.ARROW, "箭头"),
        (EditorTool.TEXT, "文字"),
    ]

    TOOL_ICONS = {
        EditorTool.PEN: "pen",
        EditorTool.RECTANGLE: "rect",
        EditorTool.CIRCLE: "circle",
        EditorTool.ARROW: "arrow",
        EditorTool.TEXT: "text",
    }

    PRESET_COLORS = ["#FF3B30", "#FF9500", "#34C759", "#007AFF", "#5856D6", "#FFFFFF"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(40)
        self.setStyleSheet(f"""
            QFrame {{
                background-color: rgba(255,255,255,0.95);
                border-radius: 8px;
                border: none;
            }}
            QToolTip {{
                background-color: rgba(0,0,0,0.7);
                color: white; border: none;
                border-radius: 4px; padding: 3px 8px;
                font-size: 11px;
            }}
        """)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 30))
        shadow.setOffset(0, 2)
        self.setGraphicsEffect(shadow)

        self._feedback_timers = {}
        self._build_ui()

    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 0, 8, 0)
        layout.setSpacing(2)

        # 标注工具
        self._tool_btns = []
        for tool_id, tip in self.TOOLS:
            btn = ToolButton(self.TOOL_ICONS[tool_id], tip)
            btn.setCheckable(True)
            btn.clicked.connect(lambda _, t=tool_id: self._on_tool_click(t))
            layout.addWidget(btn)
            self._tool_btns.append(btn)
        self._tool_btns[0].setChecked(True)

        self._sep(layout)

        # 线宽
        self._width_spin = QSpinBox()
        self._width_spin.setRange(1, 20)
        self._width_spin.setValue(EDITOR_DEFAULT_LINE_WIDTH)
        self._width_spin.setFixedSize(40, 26)
        self._width_spin.setStyleSheet(f"""
            QSpinBox {{
                background: rgba(0,0,0,0.04); border: none;
                border-radius: 4px; padding: 2px 4px;
                font-size: 12px; color: {COLORS['text_primary']};
            }}
        """)
        self._width_spin.valueChanged.connect(self.width_changed.emit)
        layout.addWidget(self._width_spin)

        self._sep(layout)

        # 颜色
        for c in self.PRESET_COLORS:
            swatch = QPushButton()
            swatch.setFixedSize(16, 16)
            swatch.setToolTip("")
            border = "1px solid rgba(0,0,0,0.1)" if c == "#FFFFFF" else "1px solid transparent"
            swatch.setStyleSheet(f"""
                QPushButton {{
                    background-color: {c}; border: {border}; border-radius: 8px;
                }}
                QPushButton:hover {{ border: 1.5px solid {COLORS['accent']}; }}
            """)
            swatch.clicked.connect(lambda _, color=c: self.color_changed.emit(QColor(color)))
            layout.addWidget(swatch)

        self._sep(layout)

        # 撤销/重做
        self._undo_btn = self._action_btn("↩", "撤销 (⌘Z)")
        self._undo_btn.clicked.connect(self._undo_with_feedback)
        layout.addWidget(self._undo_btn)

        self._redo_btn = self._action_btn("↪", "重做")
        self._redo_btn.clicked.connect(self._redo_with_feedback)
        layout.addWidget(self._redo_btn)

        self._sep(layout)

        # 贴图 / 保存
        self._pin_btn = self._action_btn("📌", "钉到屏幕")
        self._pin_btn.clicked.connect(self._pin_with_feedback)
        layout.addWidget(self._pin_btn)

        self._save_btn = self._action_btn("⬇", "保存文件")
        self._save_btn.clicked.connect(self._save_with_feedback)
        layout.addWidget(self._save_btn)

        self._sep(layout)

        # 复制 — 最右边，突出显示
        self._copy_btn = QPushButton("⎘ 复制")
        self._copy_btn.setToolTip("复制到剪贴板")
        self._copy_btn.setFixedHeight(28)
        self._copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._copy_btn.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS['accent']};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 0 12px;
                font-size: 12px;
                font-weight: 600;
            }}
            QPushButton:hover {{ background: {COLORS['accent_hover']}; }}
            QPushButton:pressed {{ background: #004EA2; }}
        """)
        self._copy_btn.clicked.connect(self._copy_with_feedback)
        layout.addWidget(self._copy_btn)

    def _action_btn(self, icon, tip):
        btn = QPushButton(icon)
        btn.setToolTip(tip)
        btn.setFixedSize(28, 28)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; border: none;
                border-radius: 6px; font-size: 14px;
                color: {COLORS['text_secondary']};
            }}
            QPushButton:hover {{ background: rgba(0,0,0,0.06); color: {COLORS['text_primary']}; }}
            QPushButton:pressed {{ background: rgba(0,0,0,0.1); }}
        """)
        return btn

    def _sep(self, layout):
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setStyleSheet("color: rgba(0,0,0,0.06);")
        sep.setFixedWidth(1)
        layout.addWidget(sep)

    def _on_tool_click(self, tool):
        for btn in self._tool_btns:
            btn.setChecked(False)
        sender = self.sender()
        if sender:
            sender.setChecked(True)
        self.tool_changed.emit(tool)

    # ── 按钮反馈动效 ────────────────────────────────

    def _flash_btn(self, btn, flash_color, original_icon, duration=600):
        """通用按钮闪烁反馈"""
        try:
            btn.setText("✓")
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: {flash_color}20; border: none;
                    border-radius: 6px; font-size: 13px;
                    color: {flash_color};
                }}
            """)
            timer = QTimer(self)  # 绑定 self 防止垃圾回收
            timer.setSingleShot(True)
            timer.timeout.connect(lambda: self._safe_restore_btn(btn, original_icon))
            timer.start(duration)
        except RuntimeError:
            pass  # 按钮已被删除

    def _safe_restore_btn(self, btn, original_icon):
        """安全恢复按钮状态"""
        try:
            btn.setText(original_icon)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent; border: none;
                    border-radius: 6px; font-size: 14px;
                    color: {COLORS['text_secondary']};
                }}
                QPushButton:hover {{ background: rgba(0,0,0,0.06); color: {COLORS['text_primary']}; }}
                QPushButton:pressed {{ background: rgba(0,0,0,0.1); }}
            """)
        except RuntimeError:
            pass  # 按钮已被删除

    def _copy_with_feedback(self):
        self.copy_requested.emit()
        try:
            original_style = self._copy_btn.styleSheet()
            self._copy_btn.setText("✓ 已复制")
            self._copy_btn.setStyleSheet(f"""
                QPushButton {{
                    background: {COLORS['success']};
                    color: white; border: none;
                    border-radius: 6px; padding: 0 12px;
                    font-size: 12px; font-weight: 600;
                }}
            """)
            QTimer.singleShot(800, lambda: self._safe_reset_copy(original_style))
        except RuntimeError:
            pass

    def _safe_reset_copy(self, original_style):
        try:
            self._copy_btn.setText("⎘ 复制")
            self._copy_btn.setStyleSheet(original_style)
        except RuntimeError:
            pass

    def _undo_with_feedback(self):
        self.undo_requested.emit()
        self._flash_btn(self._undo_btn, COLORS['accent'], "↩")

    def _redo_with_feedback(self):
        self.redo_requested.emit()
        self._flash_btn(self._redo_btn, COLORS['accent'], "↪")

    def _pin_with_feedback(self):
        self.pin_requested.emit()
        self._flash_btn(self._pin_btn, COLORS['accent'], "📌")

    def _save_with_feedback(self):
        self.save_requested.emit()
        self._flash_btn(self._save_btn, COLORS['success'], "⬇")


class ToolButton(QPushButton):
    """带精致线条图标的工具按钮"""

    def __init__(self, icon_type: str, tip: str, parent=None):
        super().__init__(parent)
        self._icon_type = icon_type
        self.setToolTip(tip)
        self.setCheckable(True)
        self.setFixedSize(30, 30)
        self.setStyleSheet(f"""
            QPushButton {{
                background: transparent; border: none;
                border-radius: 6px;
            }}
            QPushButton:hover {{ background: rgba(0,0,0,0.06); }}
            QPushButton:checked {{ background: {COLORS['accent_soft']}; }}
        """)

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        color = COLORS["accent"] if self.isChecked() else COLORS["text_secondary"]
        pen = QPen(QColor(color), 1.5)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        cx, cy = self.width() // 2, self.height() // 2

        if self._icon_type == "pen":
            painter.drawLine(cx - 6, cy + 6, cx + 4, cy - 4)
            painter.drawLine(cx + 4, cy - 4, cx + 6, cy - 6)
            painter.drawLine(cx - 6, cy + 6, cx - 4, cy + 4)
            painter.setPen(QPen(QColor(color), 1))
            painter.drawLine(cx - 6, cy + 6, cx - 7, cy + 7)
        elif self._icon_type == "rect":
            painter.drawRoundedRect(cx - 7, cy - 5, 14, 10, 1, 1)
        elif self._icon_type == "circle":
            painter.drawEllipse(QPoint(cx, cy), 6, 6)
        elif self._icon_type == "arrow":
            painter.drawLine(cx - 6, cy + 4, cx + 5, cy - 5)
            painter.drawLine(cx + 5, cy - 5, cx + 1, cy - 3)
            painter.drawLine(cx + 5, cy - 5, cx + 3, cy - 1)
        elif self._icon_type == "text":
            painter.drawLine(cx - 5, cy - 5, cx + 5, cy - 5)
            painter.drawLine(cx, cy - 5, cx, cy + 6)

        painter.end()


# ═══════════════════════════════════════════════════════════
#  浮动编辑器窗口
# ═══════════════════════════════════════════════════════════

class FloatingEditorWindow(QWidget):
    image_saved = pyqtSignal(str)
    pin_requested = pyqtSignal(QPixmap)
    closed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._drag_pos = None
        self._original_size = None
        self._setup_window()
        self._build_ui()
        self._connect_signals()

    def _setup_window(self):
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(0)

        # ── 画布容器 ─────────────────────────────────
        self._canvas_frame = QFrame()
        self._canvas_frame.setStyleSheet("""
            QFrame {
                background-color: white;
                border-radius: 6px;
                border: 1px solid rgba(0,0,0,0.06);
            }
        """)
        shadow = QGraphicsDropShadowEffect(self._canvas_frame)
        shadow.setBlurRadius(40)
        shadow.setColor(QColor(0, 0, 0, 40))
        shadow.setOffset(0, 6)
        self._canvas_frame.setGraphicsEffect(shadow)

        # 画布内部布局
        self._frame_layout = QVBoxLayout(self._canvas_frame)
        self._frame_layout.setContentsMargins(0, 0, 0, 0)
        self._frame_layout.setSpacing(0)

        # 红绿灯 — 覆盖在画布左上角
        lights_wrap = QWidget()
        lights_wrap.setStyleSheet("background: transparent; border: none;")
        lights_wrap.setFixedHeight(28)
        ll = QHBoxLayout(lights_wrap)
        ll.setContentsMargins(10, 0, 0, 0)
        self._traffic_lights = TrafficLights()
        ll.addWidget(self._traffic_lights)
        ll.addStretch()
        self._frame_layout.addWidget(lights_wrap)

        # 画布
        self._canvas = EditorCanvas()
        self._canvas.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._frame_layout.addWidget(self._canvas)

        layout.addWidget(self._canvas_frame)

        # ── 工具栏 ───────────────────────────────────
        toolbar_wrap = QWidget()
        toolbar_wrap.setStyleSheet("background: transparent;")
        tb_layout = QHBoxLayout(toolbar_wrap)
        tb_layout.setContentsMargins(0, 8, 0, 0)
        tb_layout.addStretch()
        self._toolbar = CompactToolbar()
        tb_layout.addWidget(self._toolbar)
        tb_layout.addStretch()
        layout.addWidget(toolbar_wrap)

    def _connect_signals(self):
        self._toolbar.tool_changed.connect(self._canvas.set_tool)
        self._toolbar.color_changed.connect(self._canvas.set_color)
        self._toolbar.width_changed.connect(self._canvas.set_line_width)
        self._toolbar.undo_requested.connect(self._canvas.undo)
        self._toolbar.redo_requested.connect(self._canvas.redo)
        self._toolbar.save_requested.connect(self._save)
        self._toolbar.copy_requested.connect(self._copy_to_clipboard)
        self._toolbar.pin_requested.connect(self._pin)

        # 红绿灯
        self._traffic_lights.close_clicked.connect(self._close)
        self._traffic_lights.minimize_clicked.connect(self._minimize)
        self._traffic_lights.maximize_clicked.connect(self._maximize)

    # ── 公开 API ────────────────────────────────────

    def load_image(self, path: str):
        self._canvas.set_image(path)
        img_w, img_h = self._canvas.editor.get_size()

        # Retina 屏幕修正：截图像素是 2x，画布应该显示逻辑尺寸
        ratio = QApplication.primaryScreen().devicePixelRatio()
        if ratio > 1:
            display_w = int(img_w / ratio)
            display_h = int(img_h / ratio)
        else:
            display_w = img_w
            display_h = img_h

        # 画布固定为逻辑尺寸
        self._canvas.setFixedSize(display_w, display_h)

        # 精确窗口大小
        win_w = display_w + 22
        win_h = display_h + 28 + 22 + 48

        screen = QApplication.primaryScreen().geometry()
        win_w = min(win_w, screen.width() - 60)
        win_h = min(win_h, screen.height() - 60)

        self.resize(win_w, win_h)
        self._original_size = QSize(win_w, win_h)
        self.move((screen.width() - win_w) // 2, (screen.height() - win_h) // 2)
        self.show()
        keep_window_on_top(self)
        self.raise_()
        self.activateWindow()

    # ── 红绿灯操作 ──────────────────────────────────

    def _minimize(self):
        """最小化 — 缩小到仅红绿灯可见"""
        self.resize(80, 50)

    def _maximize(self):
        """最大化 — 恢复原始尺寸或全屏"""
        if self._original_size and self.size() != self._original_size:
            self.resize(self._original_size)
        else:
            screen = QApplication.primaryScreen().geometry()
            self.resize(screen.width() - 40, screen.height() - 40)

    # ── 拖拽 ────────────────────────────────────────

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton and event.y() < 48:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._drag_pos and event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
        self.setCursor(Qt.CursorShape.ArrowCursor)

    # ── 操作 ────────────────────────────────────────

    def _save(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "保存截图", "", "PNG (*.png);;JPEG (*.jpg)")
        if path:
            self._canvas.save(path)
            self.image_saved.emit(path)

    def _copy_to_clipboard(self):
        try:
            pm = self._canvas.get_qpixmap()
            if not pm.isNull():
                QApplication.clipboard().setPixmap(pm)
        except RuntimeError:
            pass

    def _pin(self):
        pm = self._canvas.get_qpixmap()
        if not pm.isNull():
            self.pin_requested.emit(pm)

    def _close(self):
        # 关闭时丢弃截图内容，清理画布
        try:
            if self._canvas.editor:
                self._canvas.editor = None
                self._canvas.temp_pixmap = None
                self._canvas.update()
        except RuntimeError:
            pass
        self.hide()
        self.closed.emit()
