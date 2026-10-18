"""
内嵌截图编辑器 - 钉钉风格的实时标注工具
截图后直接在主窗口内编辑，不开新窗口
"""

import io
import math
from typing import Optional, List, Tuple
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QFrame, QSpinBox, QColorDialog, QInputDialog, QScrollArea,
    QSizePolicy, QApplication, QFileDialog
)
from PyQt6.QtCore import Qt, QPoint, QRect, QRectF, pyqtSignal, QSize
from PyQt6.QtGui import (
    QImage, QPixmap, QPainter, QPen, QColor, QFont,
    QMouseEvent, QPaintEvent, QKeyEvent, QBrush, QPainterPath
)

from screenshot.editor import ImageEditor
from config import EditorTool, EDITOR_DEFAULT_COLOR, EDITOR_DEFAULT_LINE_WIDTH
from ui.styles import (
    COLORS, SIZES, icon_button_style, toolbar_floating_style,
    primary_button_style, ghost_button_style, secondary_button_style
)


class EditorCanvas(QWidget):
    """编辑器画布 - 处理所有绘图交互"""

    image_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.editor: Optional[ImageEditor] = None
        self.current_tool = EditorTool.PEN
        self.current_color = QColor(EDITOR_DEFAULT_COLOR)
        self.line_width = EDITOR_DEFAULT_LINE_WIDTH

        # 绘制状态
        self._drawing = False
        self._points: List[QPoint] = []
        self._start_pt: Optional[QPoint] = None
        self._end_pt: Optional[QPoint] = None

        # 图像偏移（居中显示用）
        self._offset_x = 0
        self._offset_y = 0
        self._display_scale = 1.0

        self.temp_pixmap: Optional[QPixmap] = None
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(200, 200)

    def set_image(self, image_path: str):
        self.editor = ImageEditor(image_path)
        self._recalc_size()
        self.update()

    def set_pixmap(self, pixmap: QPixmap):
        """从 QPixmap 设置图像"""
        from PIL import Image
        qimg = pixmap.toImage().convertToFormat(QImage.Format.Format_RGBA8888)
        ptr = qimg.bits()
        ptr.setsize(qimg.sizeInBytes())
        pil_img = Image.frombytes("RGBA", (qimg.width(), qimg.height()), bytes(ptr), "raw", "RGBA")
        pil_img = pil_img.convert("RGB")

        self.editor = ImageEditor()
        self.editor.original_image = pil_img.copy()
        self.editor.image = pil_img.copy()
        self.editor.draw = __import__('PIL.ImageDraw', fromlist=['ImageDraw']).Draw(self.editor.image)
        self.editor._save_state()
        self._recalc_size()
        self.update()

    def _recalc_size(self):
        """根据图像重新计算画布尺寸"""
        if not self.editor:
            return
        img_w, img_h = self.editor.get_size()
        # 画布尺寸 = 图像尺寸（最大不超过容器）
        self.setMinimumSize(min(img_w, 1200), min(img_h, 800))

    def _get_display_rect(self) -> Tuple[int, int, int, float]:
        """获取图像在画布上的显示区域和缩放比"""
        if not self.editor:
            return 0, 0, 1.0, 1.0
        img_w, img_h = self.editor.get_size()
        canvas_w, canvas_h = self.width(), self.height()

        scale_x = canvas_w / img_w if img_w > 0 else 1
        scale_y = canvas_h / img_h if img_h > 0 else 1
        scale = min(scale_x, scale_y, 1.0)  # 不放大，只缩小

        disp_w = int(img_w * scale)
        disp_h = int(img_h * scale)
        ox = (canvas_w - disp_w) // 2
        oy = (canvas_h - disp_h) // 2

        self._offset_x = ox
        self._offset_y = oy
        self._display_scale = scale
        return ox, oy, disp_w, disp_h

    def _widget_to_image(self, pt: QPoint) -> QPoint:
        """将画布坐标转换为图像坐标"""
        if self._display_scale == 0:
            return pt
        ix = int((pt.x() - self._offset_x) / self._display_scale)
        iy = int((pt.y() - self._offset_y) / self._display_scale)
        return QPoint(ix, iy)

    def _get_qpixmap(self) -> QPixmap:
        if not self.editor:
            return QPixmap()
        buf = io.BytesIO()
        self.editor.image.save(buf, format="PNG")
        buf.seek(0)
        qimg = QImage()
        qimg.loadFromData(buf.getvalue())
        return QPixmap.fromImage(qimg)

    # ── 绘制 ──────────────────────────────────────────

    def paintEvent(self, event: QPaintEvent):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        if not self.editor:
            # 空状态
            painter.setPen(QPen(QColor(COLORS["text_hint"]), 1))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "截图后将在此显示")
            painter.end()
            return

        pixmap = self._get_qpixmap()
        if pixmap.isNull():
            painter.end()
            return

        # 计算显示区域
        ox, oy, dw, dh = self._get_display_rect()

        # 棋盘格背景（表示透明）
        self._draw_checkerboard(painter, ox, oy, dw, dh)

        # 绘制图像
        scaled = pixmap.scaled(dw, dh, Qt.AspectRatioMode.KeepAspectRatio,
                               Qt.TransformationMode.SmoothTransformation)
        painter.drawPixmap(ox, oy, scaled)

        # 绘制临时层
        if self.temp_pixmap and not self.temp_pixmap.isNull():
            painter.drawPixmap(ox, oy, self.temp_pixmap.scaled(
                dw, dh, Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation))

        painter.end()

    def _draw_checkerboard(self, painter: QPainter, x, y, w, h):
        """绘制棋盘格背景"""
        cell = 10
        painter.setPen(Qt.PenStyle.NoPen)
        for row in range(0, h, cell):
            for col in range(0, w, cell):
                if (row // cell + col // cell) % 2 == 0:
                    painter.setBrush(QColor(240, 240, 240))
                else:
                    painter.setBrush(QColor(255, 255, 255))
                painter.drawRect(x + col, y + row, cell, cell)

    # ── 鼠标事件 ──────────────────────────────────────

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton and self.editor:
            self._drawing = True
            img_pt = self._widget_to_image(event.pos())
            if self.current_tool == EditorTool.PEN:
                self._points = [img_pt]
            elif self.current_tool in (EditorTool.RECTANGLE, EditorTool.CIRCLE, EditorTool.ARROW):
                self._start_pt = img_pt
                self._end_pt = img_pt
            elif self.current_tool == EditorTool.TEXT:
                self._input_text_at(img_pt)
                self._drawing = False

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._drawing and self.editor:
            img_pt = self._widget_to_image(event.pos())
            if self.current_tool == EditorTool.PEN:
                self._points.append(img_pt)
                self._update_temp()
            elif self.current_tool in (EditorTool.RECTANGLE, EditorTool.CIRCLE, EditorTool.ARROW):
                self._end_pt = img_pt
                self._update_temp()

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton and self._drawing and self.editor:
            self._drawing = False
            img_pt = self._widget_to_image(event.pos())

            if self.current_tool == EditorTool.PEN and len(self._points) >= 2:
                pts = [(p.x(), p.y()) for p in self._points]
                self.editor.draw_pen(pts, self.current_color.name(), self.line_width)
                self._points = []
            elif self.current_tool == EditorTool.RECTANGLE and self._start_pt:
                self.editor.draw_rectangle(
                    (self._start_pt.x(), self._start_pt.y()),
                    (img_pt.x(), img_pt.y()),
                    self.current_color.name(), self.line_width)
            elif self.current_tool == EditorTool.CIRCLE and self._start_pt:
                cx = (self._start_pt.x() + img_pt.x()) // 2
                cy = (self._start_pt.y() + img_pt.y()) // 2
                r = min(abs(img_pt.x() - self._start_pt.x()),
                        abs(img_pt.y() - self._start_pt.y())) // 2
                self.editor.draw_circle((cx, cy), r, self.current_color.name(), self.line_width)
            elif self.current_tool == EditorTool.ARROW and self._start_pt:
                self.editor.draw_arrow(
                    (self._start_pt.x(), self._start_pt.y()),
                    (img_pt.x(), img_pt.y()),
                    self.current_color.name(), self.line_width)

            self.temp_pixmap = None
            self.image_changed.emit()
            self.update()

    def _input_text_at(self, pos: QPoint):
        """在指定位置输入文字"""
        text, ok = QInputDialog.getText(self, "添加文字", "输入文字内容:")
        if ok and text.strip():
            self.editor.draw_text(
                (pos.x(), pos.y()), text.strip(),
                self.current_color.name(), max(16, self.line_width * 6))
            self.image_changed.emit()
            self.update()

    def keyPressEvent(self, event: QKeyEvent):
        mod = event.modifiers()
        if event.key() == Qt.Key.Key_Z and (mod & Qt.KeyboardModifier.ControlModifier or mod & Qt.KeyboardModifier.MetaModifier):
            self.undo()
        elif event.key() == Qt.Key.Key_Y and (mod & Qt.KeyboardModifier.ControlModifier or mod & Qt.KeyboardModifier.MetaModifier):
            self.redo()

    # ── 临时绘制层 ────────────────────────────────────

    def _update_temp(self):
        """更新实时预览"""
        if not self.editor:
            return
        img_w, img_h = self.editor.get_size()
        self.temp_pixmap = QPixmap(img_w, img_h)
        self.temp_pixmap.fill(Qt.GlobalColor.transparent)

        p = QPainter(self.temp_pixmap)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(self.current_color, self.line_width)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)

        if self.current_tool == EditorTool.PEN and len(self._points) >= 2:
            for i in range(len(self._points) - 1):
                p.drawLine(self._points[i], self._points[i + 1])
        elif self.current_tool == EditorTool.RECTANGLE and self._start_pt and self._end_pt:
            p.drawRect(QRect(self._start_pt, self._end_pt))
        elif self.current_tool == EditorTool.CIRCLE and self._start_pt and self._end_pt:
            cx = (self._start_pt.x() + self._end_pt.x()) // 2
            cy = (self._start_pt.y() + self._end_pt.y()) // 2
            r = min(abs(self._end_pt.x() - self._start_pt.x()),
                    abs(self._end_pt.y() - self._start_pt.y())) // 2
            p.drawEllipse(QPoint(cx, cy), r, r)
        elif self.current_tool == EditorTool.ARROW and self._start_pt and self._end_pt:
            self._draw_arrow_preview(p)

        p.end()
        self.update()

    def _draw_arrow_preview(self, painter: QPainter):
        """绘制箭头预览"""
        painter.drawLine(self._start_pt, self._end_pt)
        dx = self._end_pt.x() - self._start_pt.x()
        dy = self._end_pt.y() - self._start_pt.y()
        angle = math.atan2(dy, dx)
        arrow_len = max(15, self.line_width * 5)
        arrow_angle = math.pi / 6
        x1 = self._end_pt.x() - arrow_len * math.cos(angle - arrow_angle)
        y1 = self._end_pt.y() - arrow_len * math.sin(angle - arrow_angle)
        x2 = self._end_pt.x() - arrow_len * math.cos(angle + arrow_angle)
        y2 = self._end_pt.y() - arrow_len * math.sin(angle + arrow_angle)
        # 画填充的箭头头部
        path = QPainterPath()
        path.moveTo(self._end_pt.x(), self._end_pt.y())
        path.lineTo(x1, y1)
        path.lineTo(x2, y2)
        path.closeSubpath()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(self.current_color))
        painter.drawPath(path)

    # ── 工具控制 ──────────────────────────────────────

    def set_tool(self, tool: str):
        self.current_tool = tool

    def set_color(self, color: QColor):
        self.current_color = color

    def set_line_width(self, width: int):
        self.line_width = width

    def undo(self):
        if self.editor and self.editor.undo():
            self.image_changed.emit()
            self.update()

    def redo(self):
        if self.editor and self.editor.redo():
            self.image_changed.emit()
            self.update()

    def reset(self):
        if self.editor:
            self.editor.reset()
            self.image_changed.emit()
            self.update()

    def get_qpixmap(self) -> QPixmap:
        return self._get_qpixmap()

    def save(self, path: str):
        if self.editor:
            self.editor.save(path)

    def has_image(self) -> bool:
        return self.editor is not None


class FloatingToolbar(QFrame):
    """浮动工具栏 - 悬浮在画布上方"""

    tool_changed = pyqtSignal(str)
    color_changed = pyqtSignal(QColor)
    width_changed = pyqtSignal(int)
    undo_requested = pyqtSignal()
    redo_requested = pyqtSignal()
    reset_requested = pyqtSignal()
    save_requested = pyqtSignal()
    copy_requested = pyqtSignal()
    pin_requested = pyqtSignal()
    close_requested = pyqtSignal()

    TOOLS = [
        (EditorTool.PEN, "✏️", "画笔"),
        (EditorTool.RECTANGLE, "⬜", "矩形"),
        (EditorTool.CIRCLE, "⭕", "圆形"),
        (EditorTool.ARROW, "➡️", "箭头"),
        (EditorTool.TEXT, "T", "文字"),
    ]

    PRESET_COLORS = [
        "#EA4335", "#FBBC04", "#34A853", "#4285F4",
        "#9334E6", "#FF6D01", "#FFFFFF", "#202124",
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(toolbar_floating_style())
        self._build_ui()

    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(2)

        # 工具按钮
        self._tool_btns = []
        for tool_id, icon, tip in self.TOOLS:
            btn = QPushButton(icon)
            btn.setToolTip(tip)
            btn.setCheckable(True)
            btn.setFixedSize(36, 36)
            btn.clicked.connect(lambda checked, t=tool_id: self._on_tool_click(t))
            layout.addWidget(btn)
            self._tool_btns.append(btn)

        self._tool_btns[0].setChecked(True)  # 默认画笔

        self._add_separator(layout)

        # 预设颜色
        for c in self.PRESET_COLORS:
            swatch = QPushButton()
            swatch.setFixedSize(24, 24)
            swatch.setToolTip(c)
            border = "2px solid #DADCE0" if c == "#FFFFFF" else "2px solid transparent"
            swatch.setStyleSheet(f"""
                QPushButton {{
                    background-color: {c};
                    border: {border};
                    border-radius: 12px;
                }}
                QPushButton:hover {{
                    border: 2px solid {COLORS['primary']};
                }}
            """)
            swatch.clicked.connect(lambda _, color=c: self._on_color_click(color))
            layout.addWidget(swatch)

        # 自定义颜色
        self._color_btn = QPushButton("🎨")
        self._color_btn.setFixedSize(28, 28)
        self._color_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: none;
                border-radius: 14px;
                font-size: 16px;
            }}
            QPushButton:hover {{ background: {COLORS['bg_hover']}; }}
        """)
        self._color_btn.clicked.connect(self._pick_custom_color)
        layout.addWidget(self._color_btn)

        self._add_separator(layout)

        # 线宽
        lbl = QLabel("粗细")
        lbl.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 12px;")
        layout.addWidget(lbl)
        self._width_spin = QSpinBox()
        self._width_spin.setRange(1, 20)
        self._width_spin.setValue(EDITOR_DEFAULT_LINE_WIDTH)
        self._width_spin.setFixedWidth(55)
        self._width_spin.valueChanged.connect(self.width_changed.emit)
        layout.addWidget(self._width_spin)

        self._add_separator(layout)

        # 操作按钮
        actions = [
            ("↩", "撤销", self.undo_requested),
            ("↪", "重做", self.redo_requested),
            ("🔄", "重置", self.reset_requested),
        ]
        for icon, tip, sig in actions:
            btn = QPushButton(icon)
            btn.setToolTip(tip)
            btn.setFixedSize(36, 36)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent; border: none;
                    border-radius: 6px; font-size: 16px;
                }}
                QPushButton:hover {{ background: {COLORS['bg_hover']}; }}
            """)
            btn.clicked.connect(sig.emit)
            layout.addWidget(btn)

        self._add_separator(layout)

        # 功能按钮
        copy_btn = QPushButton("📋")
        copy_btn.setToolTip("复制到剪贴板")
        copy_btn.setFixedSize(36, 36)
        copy_btn.setStyleSheet(f"""
            QPushButton {{ background: transparent; border: none; border-radius: 6px; font-size: 16px; }}
            QPushButton:hover {{ background: {COLORS['bg_hover']}; }}
        """)
        copy_btn.clicked.connect(self.copy_requested.emit)
        layout.addWidget(copy_btn)

        pin_btn = QPushButton("📌")
        pin_btn.setToolTip("钉到屏幕上")
        pin_btn.setFixedSize(36, 36)
        pin_btn.setStyleSheet(f"""
            QPushButton {{ background: transparent; border: none; border-radius: 6px; font-size: 16px; }}
            QPushButton:hover {{ background: {COLORS['bg_hover']}; }}
        """)
        pin_btn.clicked.connect(self.pin_requested.emit)
        layout.addWidget(pin_btn)

        save_btn = QPushButton("💾")
        save_btn.setToolTip("保存文件")
        save_btn.setFixedSize(36, 36)
        save_btn.setStyleSheet(f"""
            QPushButton {{ background: transparent; border: none; border-radius: 6px; font-size: 16px; }}
            QPushButton:hover {{ background: {COLORS['bg_hover']}; }}
        """)
        save_btn.clicked.connect(self.save_requested.emit)
        layout.addWidget(save_btn)

        self._add_separator(layout)

        # 关闭编辑器
        close_btn = QPushButton("✕")
        close_btn.setToolTip("关闭编辑器")
        close_btn.setFixedSize(36, 36)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; border: none;
                border-radius: 6px; font-size: 14px;
                color: {COLORS['text_secondary']};
            }}
            QPushButton:hover {{
                background: {COLORS['danger']}20;
                color: {COLORS['danger']};
            }}
        """)
        close_btn.clicked.connect(self.close_requested.emit)
        layout.addWidget(close_btn)

    def _add_separator(self, layout):
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setStyleSheet(f"color: {COLORS['border_light']};")
        sep.setFixedWidth(1)
        layout.addWidget(sep)

    def _on_tool_click(self, tool: str):
        for btn in self._tool_btns:
            btn.setChecked(False)
        sender = self.sender()
        if sender:
            sender.setChecked(True)
        self.tool_changed.emit(tool)

    def _on_color_click(self, color_hex: str):
        self.color_changed.emit(QColor(color_hex))

    def _pick_custom_color(self):
        color = QColorDialog.getColor(Qt.GlobalColor.red, self, "选择颜色")
        if color.isValid():
            self.color_changed.emit(color)


class InlineScreenshotEditor(QWidget):
    """内嵌截图编辑器 - 集成画布和浮动工具栏"""

    image_saved = pyqtSignal(str)
    pin_requested = pyqtSignal(QPixmap)
    closed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()
        self._connect_signals()
        self.setVisible(False)

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 容器卡片
        self._card = QFrame()
        self._card.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['bg_card']};
                border-radius: {SIZES['radius_lg']};
                border: 1px solid {COLORS['border_light']};
            }}
        """)
        card_layout = QVBoxLayout(self._card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)

        # 顶部标题栏
        header = QFrame()
        header.setStyleSheet("QFrame { background: transparent; border: none; }")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(16, 10, 16, 10)

        title = QLabel("🖼  截图编辑")
        title.setStyleSheet(f"""
            font-size: 14px; font-weight: 600;
            color: {COLORS['text_primary']};
        """)
        header_layout.addWidget(title)
        header_layout.addStretch()

        hint = QLabel("在截图上直接标注  ·  Cmd+Z 撤销")
        hint.setStyleSheet(f"font-size: 12px; color: {COLORS['text_hint']};")
        header_layout.addWidget(hint)

        card_layout.addWidget(header)

        # 分隔线
        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setStyleSheet(f"color: {COLORS['border_light']};")
        divider.setFixedHeight(1)
        card_layout.addWidget(divider)

        # 画布区域（可滚动）
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setStyleSheet(f"""
            QScrollArea {{
                border: none;
                background-color: {COLORS['bg_main']};
            }}
        """)
        self._canvas = EditorCanvas()
        self._scroll.setWidget(self._canvas)
        self._canvas.setMinimumHeight(350)
        card_layout.addWidget(self._scroll)

        main_layout.addWidget(self._card)

        # 浮动工具栏（放在卡片外面底部居中）
        self._toolbar = FloatingToolbar()

        toolbar_wrapper = QWidget()
        toolbar_wrapper.setStyleSheet("background: transparent;")
        tb_layout = QHBoxLayout(toolbar_wrapper)
        tb_layout.setContentsMargins(0, 4, 0, 0)
        tb_layout.addStretch()
        tb_layout.addWidget(self._toolbar)
        tb_layout.addStretch()
        main_layout.addWidget(toolbar_wrapper)

    def _connect_signals(self):
        self._toolbar.tool_changed.connect(self._canvas.set_tool)
        self._toolbar.color_changed.connect(self._canvas.set_color)
        self._toolbar.width_changed.connect(self._canvas.set_line_width)
        self._toolbar.undo_requested.connect(self._canvas.undo)
        self._toolbar.redo_requested.connect(self._canvas.redo)
        self._toolbar.reset_requested.connect(self._canvas.reset)
        self._toolbar.save_requested.connect(self._save)
        self._toolbar.copy_requested.connect(self._copy_to_clipboard)
        self._toolbar.pin_requested.connect(self._pin)
        self._toolbar.close_requested.connect(self._close)

    # ── 公开 API ──────────────────────────────────────

    def load_image(self, path: str):
        """加载图片并显示编辑器"""
        self._canvas.set_image(path)
        self.setVisible(True)

    def is_visible(self) -> bool:
        return self.isVisible()

    # ── 内部方法 ──────────────────────────────────────

    def _save(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "保存截图", "", "PNG (*.png);;JPEG (*.jpg);;All Files (*)")
        if path:
            self._canvas.save(path)
            self.image_saved.emit(path)

    def _copy_to_clipboard(self):
        pm = self._canvas.get_qpixmap()
        if not pm.isNull():
            QApplication.clipboard().setPixmap(pm)

    def _pin(self):
        pm = self._canvas.get_qpixmap()
        if not pm.isNull():
            self.pin_requested.emit(pm)

    def _close(self):
        self.setVisible(False)
        self.closed.emit()
