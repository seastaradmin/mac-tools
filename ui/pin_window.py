"""
贴图窗口 - 将截图钉在屏幕上
"""

from PyQt6.QtWidgets import (
    QWidget, QApplication, QMenu, QGraphicsDropShadowEffect,
    QVBoxLayout, QLabel
)
from PyQt6.QtCore import Qt, QPoint, QRectF, pyqtSignal, QTimer
from PyQt6.QtGui import (
    QPixmap, QPainter, QPen, QColor, QMouseEvent,
    QCursor, QWheelEvent, QPaintEvent
)

from ui.styles import COLORS
from ui.window_levels import keep_window_on_top


class PinWindow(QWidget):
    """贴图窗口 - 始终置顶的浮动图片"""

    closed = pyqtSignal(object)  # 关闭时发射，传递自身引用

    ZOOM_STEP = 0.1
    ZOOM_MIN = 0.2
    ZOOM_MAX = 5.0
    BORDER_WIDTH = 2
    MIN_SIZE = 80

    def __init__(self, pixmap: QPixmap, parent=None):
        super().__init__(parent)
        self._pixmap = pixmap
        self._zoom = 1.0
        self._dragging = False
        self._resizing = False
        self._resize_edge = None
        self._drag_start = QPoint()
        self._original_pos = QPoint()
        self._original_size = None

        self._setup_window()

    # ── 初始化 ──────────────────────────────────────────

    def _setup_window(self):
        """配置窗口属性"""
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setMouseTracking(True)

        image_w, image_h = self._pixmap_logical_size()
        screen = QApplication.primaryScreen().availableGeometry()
        max_w = max(self.MIN_SIZE, screen.width() - 120)
        max_h = max(self.MIN_SIZE, screen.height() - 120)
        self._zoom = min(1.0, max_w / image_w, max_h / image_h)
        w = int(image_w * self._zoom)
        h = int(image_h * self._zoom)
        self.resize(w + self.BORDER_WIDTH * 2, h + self.BORDER_WIDTH * 2)

        # 放到屏幕右上角偏移
        self.move(screen.x() + screen.width() - self.width() - 60, screen.y() + 80)

        # 阴影效果
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 40))
        shadow.setOffset(0, 4)

    def _pixmap_logical_size(self):
        size = self._pixmap.deviceIndependentSize()
        return max(1, int(round(size.width()))), max(1, int(round(size.height())))

    def _image_target_rect(self, target_w, target_h):
        image_w, image_h = self._pixmap_logical_size()
        image_ratio = image_w / image_h
        target_ratio = target_w / target_h
        if target_ratio > image_ratio:
            h = target_h
            w = h * image_ratio
        else:
            w = target_w
            h = w / image_ratio
        x = self.BORDER_WIDTH + (target_w - w) / 2
        y = self.BORDER_WIDTH + (target_h - h) / 2
        return QRectF(x, y, w, h)

    def showEvent(self, event):
        super().showEvent(event)
        keep_window_on_top(self)

    # ── 绘制 ──────────────────────────────────────────

    def paintEvent(self, event: QPaintEvent):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        # 白色边框背景
        painter.setPen(QPen(QColor(COLORS["border"]), self.BORDER_WIDTH))
        painter.setBrush(QColor(COLORS["bg_card"]))
        painter.drawRect(QRectF(
            self.BORDER_WIDTH / 2, self.BORDER_WIDTH / 2,
            self.width() - self.BORDER_WIDTH, self.height() - self.BORDER_WIDTH
        ))

        # 绘制图片
        target_w = self.width() - self.BORDER_WIDTH * 2
        target_h = self.height() - self.BORDER_WIDTH * 2
        if target_w > 0 and target_h > 0:
            painter.drawPixmap(
                self._image_target_rect(target_w, target_h),
                self._pixmap,
                QRectF(self._pixmap.rect())
            )

        # 绘制关闭按钮 (右上角)
        close_size = 20
        close_rect = QRectF(self.width() - close_size - 4, 4, close_size, close_size)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(COLORS["danger"]))
        painter.drawEllipse(close_rect)

        # 画 X
        painter.setPen(QPen(QColor("white"), 2))
        margin = 5
        painter.drawLine(
            QPoint(int(close_rect.x()) + margin, int(close_rect.y()) + margin),
            QPoint(int(close_rect.right()) - margin, int(close_rect.bottom()) - margin)
        )
        painter.drawLine(
            QPoint(int(close_rect.right()) - margin, int(close_rect.y()) + margin),
            QPoint(int(close_rect.x()) + margin, int(close_rect.bottom()) - margin)
        )

        painter.end()

    # ── 鼠标事件 ──────────────────────────────────────

    def _in_close_button(self, pos: QPoint) -> bool:
        close_size = 20
        close_rect = QRectF(self.width() - close_size - 4, 4, close_size, close_size)
        return close_rect.contains(pos.x(), pos.y())

    def _get_resize_edge(self, pos: QPoint):
        """检测是否在边缘可调整大小"""
        margin = 8
        edge = None
        if pos.x() < margin:
            edge = "left"
        elif pos.x() > self.width() - margin:
            edge = "right"
        if pos.y() < margin:
            edge = "top" if edge is None else edge + "-top"
        elif pos.y() > self.height() - margin:
            edge = "bottom" if edge is None else edge + "-bottom"
        return edge

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            if self._in_close_button(event.pos()):
                self.close_pin()
                return

            edge = self._get_resize_edge(event.pos())
            if edge:
                self._resizing = True
                self._resize_edge = edge
                self._drag_start = event.globalPosition().toPoint()
                self._original_size = self.size()
                self._original_pos = self.pos()
            else:
                self._dragging = True
                self._drag_start = event.globalPosition().toPoint()
                self._original_pos = self.pos()

    def mouseMoveEvent(self, event: QMouseEvent):
        pos = event.pos()

        # 更新光标
        edge = self._get_resize_edge(pos)
        if edge:
            cursor_map = {
                "left": Qt.CursorShape.SizeHorCursor,
                "right": Qt.CursorShape.SizeHorCursor,
                "top": Qt.CursorShape.SizeVerCursor,
                "bottom": Qt.CursorShape.SizeVerCursor,
                "left-top": Qt.CursorShape.SizeFDiagCursor,
                "right-bottom": Qt.CursorShape.SizeFDiagCursor,
                "left-bottom": Qt.CursorShape.SizeBDiagCursor,
                "right-top": Qt.CursorShape.SizeBDiagCursor,
            }
            self.setCursor(cursor_map.get(edge, Qt.CursorShape.ArrowCursor))
        elif self._in_close_button(pos):
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor if not self._dragging else Qt.CursorShape.ClosedHandCursor)

        if self._dragging:
            delta = event.globalPosition().toPoint() - self._drag_start
            self.move(self._original_pos + delta)

        elif self._resizing and self._original_size:
            delta = event.globalPosition().toPoint() - self._drag_start
            new_w = self._original_size.width()
            new_h = self._original_size.height()
            new_x = self._original_pos.x()
            new_y = self._original_pos.y()

            if "right" in (self._resize_edge or ""):
                new_w = max(self.MIN_SIZE, self._original_size.width() + delta.x())
            if "left" in (self._resize_edge or ""):
                new_w = max(self.MIN_SIZE, self._original_size.width() - delta.x())
                new_x = self._original_pos.x() + (self._original_size.width() - new_w)
            if "bottom" in (self._resize_edge or ""):
                new_h = max(self.MIN_SIZE, self._original_size.height() + delta.y())
            if "top" in (self._resize_edge or ""):
                new_h = max(self.MIN_SIZE, self._original_size.height() - delta.y())
                new_y = self._original_pos.y() + (self._original_size.height() - new_h)

            self.setGeometry(new_x, new_y, new_w, new_h)

    def mouseReleaseEvent(self, event: QMouseEvent):
        self._dragging = False
        self._resizing = False
        self._resize_edge = None

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        """双击重置为原始大小"""
        self._zoom = 1.0
        image_w, image_h = self._pixmap_logical_size()
        w = image_w + self.BORDER_WIDTH * 2
        h = image_h + self.BORDER_WIDTH * 2
        self.resize(w, h)
        self.update()

    def wheelEvent(self, event: QWheelEvent):
        """滚轮缩放"""
        delta = event.angleDelta().y()
        if delta > 0:
            self._zoom = min(self.ZOOM_MAX, self._zoom + self.ZOOM_STEP)
        else:
            self._zoom = max(self.ZOOM_MIN, self._zoom - self.ZOOM_STEP)

        image_w, image_h = self._pixmap_logical_size()
        new_w = int(image_w * self._zoom) + self.BORDER_WIDTH * 2
        new_h = int(image_h * self._zoom) + self.BORDER_WIDTH * 2
        self.resize(max(self.MIN_SIZE, new_w), max(self.MIN_SIZE, new_h))
        self.update()

    # ── 右键菜单 ──────────────────────────────────────

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{
                background-color: {COLORS['bg_card']};
                border: 1px solid {COLORS['border_light']};
                border-radius: 12px;
                padding: 6px;
            }}
            QMenu::item {{
                padding: 8px 24px;
                border-radius: 6px;
            }}
            QMenu::item:selected {{
                background-color: {COLORS['primary_light']};
                color: {COLORS['primary']};
            }}
        """)

        act_copy = menu.addAction("📋  复制到剪贴板")
        act_save = menu.addAction("💾  保存到文件")
        act_opacity = menu.addMenu("🔍  透明度")
        for v in [100, 80, 60, 40]:
            act_opacity.addAction(f"{v}%")
        menu.addSeparator()
        act_close = menu.addAction("✕  关闭")

        action = menu.exec(event.globalPosition().toPoint())
        if action == act_copy:
            QApplication.clipboard().setPixmap(self._pixmap)
        elif action == act_save:
            from PyQt6.QtWidgets import QFileDialog
            path, _ = QFileDialog.getSaveFileName(
                self, "保存贴图", "", "PNG (*.png);;JPEG (*.jpg)"
            )
            if path:
                self._pixmap.save(path)
        elif action == act_close:
            self.close_pin()
        elif action and action.parentWidget() == act_opacity:
            opacity = int(action.text().replace("%", "")) / 100
            self.setWindowOpacity(opacity)

    # ── 公开方法 ──────────────────────────────────────

    def close_pin(self):
        """关闭贴图"""
        self.closed.emit(self)
        self.close()

    def get_pixmap(self) -> QPixmap:
        return self._pixmap
