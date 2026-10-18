"""
Fullscreen screenshot overlay with in-place annotation.
"""

import math
import subprocess
from datetime import datetime

from PyQt6.QtWidgets import (
    QWidget, QFrame, QHBoxLayout, QPushButton, QSpinBox, QColorDialog,
    QFileDialog, QApplication, QInputDialog
)
from PyQt6.QtCore import Qt, pyqtSignal, QPoint, QRect, QRectF
from PyQt6.QtGui import (
    QColor, QCursor, QGuiApplication, QPainter, QPainterPath, QPen, QPixmap,
    QShortcut, QKeySequence
)

from config import SCREENSHOT_DIR, TEMP_DIR, EDITOR_DEFAULT_LINE_WIDTH, EditorTool
from ui.styles import COLORS


class ScreenshotToolbar(QFrame):
    tool_changed = pyqtSignal(str)
    color_changed = pyqtSignal(QColor)
    width_changed = pyqtSignal(int)
    undo_requested = pyqtSignal()
    save_requested = pyqtSignal()
    copy_requested = pyqtSignal()
    pin_requested = pyqtSignal()
    cancel_requested = pyqtSignal()

    TOOLS = [
        (EditorTool.PEN, "pen", "画笔"),
        (EditorTool.RECTANGLE, "rect", "矩形"),
        (EditorTool.ARROW, "arrow", "箭头"),
        (EditorTool.TEXT, "text", "文字"),
    ]

    COLORS = ["#ff3b30", "#ff9500", "#34c759", "#007aff", "#5856d6", "#ffffff"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(48)
        self.setStyleSheet("""
            QFrame {
                background-color: rgba(255, 255, 255, 0.96);
                border-radius: 8px;
                border: 1px solid rgba(0, 0, 0, 0.08);
            }
        """)
        self._build_ui()

    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(6)

        self._tool_buttons = []
        for tool, icon, tip in self.TOOLS:
            btn = OverlayToolButton(icon, tip)
            btn.setCheckable(True)
            btn.clicked.connect(lambda _checked, t=tool: self._select_tool(t))
            layout.addWidget(btn)
            self._tool_buttons.append(btn)
        self._tool_buttons[0].setChecked(True)

        self._sep(layout)

        width = QSpinBox()
        width.setRange(1, 20)
        width.setValue(EDITOR_DEFAULT_LINE_WIDTH)
        width.setFixedSize(44, 30)
        width.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        width.setAlignment(Qt.AlignmentFlag.AlignCenter)
        width.setStyleSheet("""
            QSpinBox {
                background: rgba(17, 24, 39, 0.05);
                border: 1px solid rgba(17, 24, 39, 0.07);
                border-radius: 7px;
                color: #111827;
                font-size: 13px;
                font-weight: 600;
            }
        """)
        width.valueChanged.connect(self.width_changed.emit)
        layout.addWidget(width)

        self._sep(layout)

        for color in self.COLORS:
            swatch = QPushButton()
            swatch.setFixedSize(22, 22)
            border = "1px solid rgba(0,0,0,0.16)" if color == "#ffffff" else "1px solid transparent"
            swatch.setStyleSheet(f"""
                QPushButton {{
                    background-color: {color};
                    border: {border};
                    border-radius: 11px;
                }}
                QPushButton:hover {{ border: 2px solid #111827; }}
            """)
            swatch.clicked.connect(lambda _checked, c=color: self.color_changed.emit(QColor(c)))
            layout.addWidget(swatch)

        custom = OverlayToolButton("palette", "自定义颜色")
        custom.clicked.connect(self._pick_color)
        layout.addWidget(custom)

        self._sep(layout)

        undo = OverlayToolButton("undo", "撤销")
        undo.clicked.connect(self.undo_requested.emit)
        layout.addWidget(undo)

        cancel = OverlayToolButton("close", "取消")
        cancel.clicked.connect(self.cancel_requested.emit)
        layout.addWidget(cancel)

        save = OverlayToolButton("download", "保存")
        save.clicked.connect(self.save_requested.emit)
        layout.addWidget(save)

        pin = OverlayToolButton("pin", "贴到桌面")
        pin.clicked.connect(self.pin_requested.emit)
        layout.addWidget(pin)

        copy = CopyButton()
        copy.clicked.connect(self.copy_requested.emit)
        layout.addWidget(copy)

    def _select_tool(self, tool):
        for btn in self._tool_buttons:
            btn.setChecked(False)
        sender = self.sender()
        if sender:
            sender.setChecked(True)
        self.tool_changed.emit(tool)

    def _pick_color(self):
        color = QColorDialog.getColor(parent=self)
        if color.isValid():
            self.color_changed.emit(color)

    def _sep(self, layout):
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setFixedWidth(1)
        sep.setStyleSheet("color: rgba(0,0,0,0.08);")
        layout.addWidget(sep)


class OverlayToolButton(QPushButton):
    def __init__(self, icon_type, tip, parent=None):
        super().__init__(parent)
        self._icon_type = icon_type
        self.setToolTip(tip)
        self.setFixedSize(32, 32)
        self.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: none;
                border-radius: 6px;
            }}
            QPushButton:hover {{ background: rgba(0,0,0,0.07); }}
            QPushButton:checked {{ background: {COLORS['accent_soft']}; }}
        """)

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = QColor(COLORS["accent"] if self.isChecked() else "#4b5563")
        pen = QPen(color, 1.8)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        cx, cy = self.width() // 2, self.height() // 2

        if self._icon_type == "pen":
            painter.drawLine(cx - 7, cy + 7, cx + 5, cy - 5)
            painter.drawLine(cx + 5, cy - 5, cx + 7, cy - 7)
        elif self._icon_type == "rect":
            painter.drawRoundedRect(cx - 8, cy - 6, 16, 12, 1, 1)
        elif self._icon_type == "arrow":
            painter.drawLine(cx - 7, cy + 5, cx + 6, cy - 6)
            painter.drawLine(cx + 6, cy - 6, cx + 1, cy - 4)
            painter.drawLine(cx + 6, cy - 6, cx + 4, cy - 1)
        elif self._icon_type == "text":
            painter.drawLine(cx - 6, cy - 6, cx + 6, cy - 6)
            painter.drawLine(cx, cy - 6, cx, cy + 7)
        elif self._icon_type == "palette":
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#ff3b30"))
            painter.drawEllipse(QPoint(cx - 4, cy - 5), 3, 3)
            painter.setBrush(QColor("#34c759"))
            painter.drawEllipse(QPoint(cx + 4, cy - 3), 3, 3)
            painter.setBrush(QColor("#007aff"))
            painter.drawEllipse(QPoint(cx, cy + 5), 3, 3)
        elif self._icon_type == "undo":
            painter.drawLine(cx - 5, cy - 4, cx - 10, cy + 1)
            painter.drawLine(cx - 5, cy + 6, cx - 10, cy + 1)
            painter.drawArc(cx - 8, cy - 7, 18, 14, 40 * 16, 260 * 16)
        elif self._icon_type == "close":
            painter.drawLine(cx - 6, cy - 6, cx + 6, cy + 6)
            painter.drawLine(cx + 6, cy - 6, cx - 6, cy + 6)
        elif self._icon_type == "download":
            painter.drawLine(cx, cy - 8, cx, cy + 4)
            painter.drawLine(cx - 5, cy - 1, cx, cy + 4)
            painter.drawLine(cx + 5, cy - 1, cx, cy + 4)
            painter.drawLine(cx - 7, cy + 8, cx + 7, cy + 8)
        elif self._icon_type == "pin":
            painter.setBrush(color)
            painter.drawEllipse(QPoint(cx - 4, cy - 7), 3, 3)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawLine(cx - 2, cy - 5, cx + 5, cy + 2)
            painter.drawLine(cx - 9, cy - 1, cx + 1, cy - 11)
            painter.drawLine(cx + 5, cy + 2, cx - 6, cy + 9)
            painter.drawLine(cx - 7, cy + 9, cx - 4, cy + 6)
        painter.end()


class CopyButton(QPushButton):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setToolTip("复制到剪贴板")
        self.setFixedSize(82, 32)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS['accent']};
                border: none;
                border-radius: 8px;
            }}
            QPushButton:hover {{ background: {COLORS['accent_hover']}; }}
        """)

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor("white"), 1.5))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(12, 10, 9, 11, 2, 2)
        painter.drawRoundedRect(16, 8, 9, 11, 2, 2)
        font = painter.font()
        font.setPointSize(12)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(QRect(30, 0, 46, self.height()), Qt.AlignmentFlag.AlignCenter, "复制")
        painter.end()


class ScreenshotOverlay(QWidget):
    completed = pyqtSignal(str)
    pin_requested = pyqtSignal(QPixmap)
    cancelled = pyqtSignal()

    HANDLE_NONE = "none"
    HANDLE_MOVE = "move"
    MIN_SELECTION = 12

    def __init__(self, parent=None):
        super().__init__(parent)
        self._screen_pixmap = QPixmap()
        self._base_pixmap = QPixmap()
        self._edit_pixmap = QPixmap()
        self._temp_pixmap = QPixmap()
        self._selection = QRect()
        self._select_start = QPoint()
        self._draw_start = QPoint()
        self._last_point = QPoint()
        self._is_selecting = False
        self._is_drawing = False
        self._mode = "select"
        self._tool = EditorTool.PEN
        self._color = QColor("#ff3b30")
        self._line_width = EDITOR_DEFAULT_LINE_WIDTH
        self._undo_stack = []
        self._image_scale_x = 1.0
        self._image_scale_y = 1.0

        self._setup_window()
        self._toolbar = ScreenshotToolbar(self)
        self._toolbar.hide()
        self._connect_toolbar()
        QShortcut(QKeySequence(Qt.Key.Key_Escape), self, activated=self.cancel)

    def _setup_window(self):
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setMouseTracking(True)
        self.setCursor(QCursor(Qt.CursorShape.CrossCursor))

    def _connect_toolbar(self):
        self._toolbar.tool_changed.connect(self._set_tool)
        self._toolbar.color_changed.connect(self._set_color)
        self._toolbar.width_changed.connect(self._set_width)
        self._toolbar.undo_requested.connect(self.undo)
        self._toolbar.save_requested.connect(self.save)
        self._toolbar.copy_requested.connect(self.copy)
        self._toolbar.pin_requested.connect(self.pin)
        self._toolbar.cancel_requested.connect(self.cancel)

    def _set_tool(self, tool):
        self._tool = tool

    def _set_color(self, color):
        if color.isValid():
            self._color = color

    def _set_width(self, width):
        self._line_width = width

    def start(self):
        screen = QGuiApplication.primaryScreen()
        if not screen:
            return False
        self.setGeometry(screen.geometry())
        self._screen_pixmap = self._capture_desktop_pixmap(screen)
        if self._screen_pixmap.isNull():
            return False
        self._sync_image_scale()
        self._selection = QRect()
        self._base_pixmap = QPixmap()
        self._edit_pixmap = QPixmap()
        self._temp_pixmap = QPixmap()
        self._undo_stack.clear()
        self._mode = "select"
        self._toolbar.hide()
        self.show()
        self.raise_()
        self.activateWindow()
        return True

    def _capture_desktop_pixmap(self, screen):
        path = TEMP_DIR / f"overlay_full_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.png"
        try:
            result = subprocess.run(
                ["screencapture", "-x", str(path)],
                check=False,
                capture_output=True,
                text=True,
            )
            if result.returncode == 0 and path.exists():
                pixmap = QPixmap(str(path))
                if not pixmap.isNull():
                    return pixmap
        except Exception as e:
            print(f"系统截图失败，回退到 Qt 截图: {e}")
        finally:
            try:
                path.unlink(missing_ok=True)
            except Exception:
                pass
        return screen.grabWindow(0)

    def _sync_image_scale(self):
        if self.width() <= 0 or self.height() <= 0 or self._screen_pixmap.isNull():
            self._image_scale_x = 1.0
            self._image_scale_y = 1.0
            return
        self._image_scale_x = self._screen_pixmap.width() / self.width()
        self._image_scale_y = self._screen_pixmap.height() / self.height()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.drawPixmap(self.rect(), self._screen_pixmap)

        if self._selection.isNull():
            painter.fillRect(self.rect(), QColor(0, 0, 0, 96))
            painter.end()
            return

        selection = self._selection.normalized()
        path = QPainterPath()
        path.addRect(QRectF(self.rect()))
        path.addRect(QRectF(selection))
        painter.fillPath(path, QColor(0, 0, 0, 112))

        if self._mode == "edit" and not self._edit_pixmap.isNull():
            painter.drawPixmap(selection, self._edit_pixmap)
            if not self._temp_pixmap.isNull():
                painter.drawPixmap(selection, self._temp_pixmap)

        border = QPen(QColor("#1677ff"), 2)
        border.setCosmetic(True)
        painter.setPen(border)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(selection.adjusted(0, 0, -1, -1))
        painter.end()

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        pos = event.position().toPoint()
        if self._mode == "select":
            self._is_selecting = True
            self._select_start = pos
            self._selection = QRect(pos, pos)
            self.update()
            return

        if self._selection.contains(pos):
            self._is_drawing = True
            self._draw_start = self._to_image_pos(pos)
            self._last_point = self._draw_start
            if self._tool == EditorTool.TEXT:
                self._is_drawing = False
                self._add_text(self._draw_start)
            self._save_undo_state()

    def mouseMoveEvent(self, event):
        pos = event.position().toPoint()
        if self._is_selecting:
            self._selection = QRect(self._select_start, pos).normalized()
            self.update()
            return

        if not self._is_drawing or self._edit_pixmap.isNull():
            return

        image_pos = self._to_image_pos(pos)
        if self._tool == EditorTool.PEN:
            painter = QPainter(self._edit_pixmap)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            pen = QPen(self._color, self._scaled_width())
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen)
            painter.drawLine(self._last_point, image_pos)
            painter.end()
            self._last_point = image_pos
        else:
            self._temp_pixmap = QPixmap(self._edit_pixmap.size())
            self._temp_pixmap.fill(Qt.GlobalColor.transparent)
            painter = QPainter(self._temp_pixmap)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            self._paint_shape(painter, self._draw_start, image_pos)
            painter.end()
        self.update()

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        if self._is_selecting:
            self._is_selecting = False
            if self._selection.width() >= self.MIN_SELECTION and self._selection.height() >= self.MIN_SELECTION:
                self._enter_edit_mode()
            else:
                self._selection = QRect()
                self.update()
            return

        if self._is_drawing:
            self._is_drawing = False
            if not self._temp_pixmap.isNull():
                painter = QPainter(self._edit_pixmap)
                painter.drawPixmap(0, 0, self._temp_pixmap)
                painter.end()
                self._temp_pixmap = QPixmap()
            self.update()

    def _enter_edit_mode(self):
        self._selection = self._selection.normalized()
        self._mode = "edit"
        self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
        self._base_pixmap = self._screen_pixmap.copy(self._selection_to_image_rect())
        self._edit_pixmap = self._base_pixmap.copy()
        self._undo_stack = [self._edit_pixmap.copy()]
        self._position_toolbar()
        self._toolbar.show()
        self.update()

    def _position_toolbar(self):
        selection = self._selection.normalized()
        toolbar_w = max(760, self._toolbar.sizeHint().width())
        toolbar_h = self._toolbar.height()
        self._toolbar.setFixedWidth(min(toolbar_w, self.width() - 24))
        x = selection.left()
        if x + self._toolbar.width() > self.width() - 12:
            x = self.width() - self._toolbar.width() - 12
        x = max(12, x)
        y = selection.bottom() + 10
        if y + toolbar_h > self.height() - 12:
            y = selection.top() - toolbar_h - 10
        y = max(12, y)
        self._toolbar.move(x, y)

    def _to_image_pos(self, pos):
        selection = self._selection.normalized()
        x = int((pos.x() - selection.left()) * self._image_scale_x)
        y = int((pos.y() - selection.top()) * self._image_scale_y)
        x = max(0, min(x, self._edit_pixmap.width() - 1))
        y = max(0, min(y, self._edit_pixmap.height() - 1))
        return QPoint(x, y)

    def _selection_to_image_rect(self):
        selection = self._selection.normalized()
        x = int(selection.left() * self._image_scale_x)
        y = int(selection.top() * self._image_scale_y)
        w = max(1, int(selection.width() * self._image_scale_x))
        h = max(1, int(selection.height() * self._image_scale_y))
        return QRect(x, y, w, h).intersected(self._screen_pixmap.rect())

    def _scaled_width(self):
        scale = max(self._image_scale_x, self._image_scale_y, 1.0)
        return max(1, int(self._line_width * scale))

    def _paint_shape(self, painter, start, end):
        pen = QPen(self._color, self._scaled_width())
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        if self._tool == EditorTool.RECTANGLE:
            painter.drawRect(QRect(start, end).normalized())
        elif self._tool == EditorTool.ARROW:
            painter.drawLine(start, end)
            dx = end.x() - start.x()
            dy = end.y() - start.y()
            angle = math.atan2(dy, dx)
            arrow_len = max(14, self._scaled_width() * 5)
            for sign in (-1, 1):
                x = end.x() - arrow_len * math.cos(angle + sign * math.pi / 6)
                y = end.y() - arrow_len * math.sin(angle + sign * math.pi / 6)
                painter.drawLine(end, QPoint(int(x), int(y)))

    def _add_text(self, pos):
        text, ok = QInputDialog.getText(self, "文字", "输入文字:")
        if not ok or not text.strip():
            return
        painter = QPainter(self._edit_pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(self._color, 1))
        font = painter.font()
        font.setPointSize(max(14, self._scaled_width() * 5))
        painter.setFont(font)
        painter.drawText(pos, text.strip())
        painter.end()
        self.update()

    def _save_undo_state(self):
        if self._edit_pixmap.isNull():
            return
        self._undo_stack.append(self._edit_pixmap.copy())
        if len(self._undo_stack) > 30:
            self._undo_stack.pop(0)

    def undo(self):
        if len(self._undo_stack) <= 1:
            return
        self._undo_stack.pop()
        self._edit_pixmap = self._undo_stack[-1].copy()
        self._temp_pixmap = QPixmap()
        self.update()

    def save(self):
        if self._edit_pixmap.isNull():
            return
        default = SCREENSHOT_DIR / f"overlay_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        path, _ = QFileDialog.getSaveFileName(self, "保存截图", str(default), "PNG (*.png);;JPEG (*.jpg)")
        if path:
            self._edit_pixmap.save(path)
            self.completed.emit(path)
            self.close()

    def copy(self):
        if self._edit_pixmap.isNull():
            return
        QApplication.clipboard().setPixmap(self._edit_pixmap)
        self.completed.emit("")
        self.close()

    def pin(self):
        if self._edit_pixmap.isNull():
            return
        pixmap = self._edit_pixmap.copy()
        pixmap.setDevicePixelRatio(max(self._image_scale_x, self._image_scale_y, 1.0))
        self.pin_requested.emit(pixmap)
        self.close()

    def cancel(self):
        self.cancelled.emit()
        self.close()

    def closeEvent(self, event):
        self._toolbar.hide()
        super().closeEvent(event)
