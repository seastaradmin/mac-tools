"""
图像编辑窗口 - 类似钉钉的截图编辑功能
"""

import sys
from typing import Optional, List, Tuple
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QPushButton, QLabel, QColorDialog, QSpinBox,
    QToolBar, QSizePolicy, QFileDialog, QApplication
)
from PyQt6.QtCore import Qt, QPoint, QRect, pyqtSignal
from PyQt6.QtGui import (
    QImage, QPixmap, QPainter, QPen, QColor, 
    QMouseEvent, QPaintEvent, QKeyEvent, QIcon
)

from screenshot.editor import ImageEditor
from config import EditorTool, EDITOR_DEFAULT_COLOR, EDITOR_DEFAULT_LINE_WIDTH


class CanvasWidget(QWidget):
    """画布组件"""
    
    # 信号
    image_changed = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.editor: Optional[ImageEditor] = None
        self.current_tool = EditorTool.PEN
        self.current_color = QColor(EDITOR_DEFAULT_COLOR)
        self.line_width = EDITOR_DEFAULT_LINE_WIDTH
        
        # 绘制状态
        self.is_drawing = False
        self.last_point: Optional[QPoint] = None
        self.current_points: List[QPoint] = []
        
        # 矩形/圆形绘制
        self.start_point: Optional[QPoint] = None
        self.end_point: Optional[QPoint] = None
        
        # 文字输入
        self.text_position: Optional[QPoint] = None
        self.text_input: str = ""
        
        # 临时绘制层
        self.temp_pixmap: Optional[QPixmap] = None
        
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    
    def set_image(self, image_path: str):
        """设置要编辑的图像"""
        self.editor = ImageEditor(image_path)
        self.update()
    
    def set_pil_image(self, pil_image):
        """从PIL图像设置"""
        import io
        from PIL import Image
        
        # 转换为QImage
        buffer = io.BytesIO()
        pil_image.save(buffer, format="PNG")
        buffer.seek(0)
        
        qimage = QImage()
        qimage.loadFromData(buffer.getvalue())
        
        self.editor = ImageEditor()
        self.editor.image = pil_image
        self.editor.draw = __import__('PIL.ImageDraw', fromlist=['ImageDraw']).Draw(pil_image)
        
        self.update()
    
    def get_qpixmap(self) -> QPixmap:
        """获取当前图像的QPixmap"""
        if not self.editor:
            return QPixmap()
        
        # 将PIL图像转换为QPixmap
        import io
        buffer = io.BytesIO()
        self.editor.image.save(buffer, format="PNG")
        buffer.seek(0)
        
        qimage = QImage()
        qimage.loadFromData(buffer.getvalue())
        return QPixmap.fromImage(qimage)
    
    def paintEvent(self, event: QPaintEvent):
        """绘制事件"""
        painter = QPainter(self)
        
        if self.editor:
            # 绘制主图像
            pixmap = self.get_qpixmap()
            if not pixmap.isNull():
                # 缩放以适应窗口
                scaled_pixmap = pixmap.scaled(
                    self.size(), 
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                
                # 居中绘制
                x = (self.width() - scaled_pixmap.width()) // 2
                y = (self.height() - scaled_pixmap.height()) // 2
                painter.drawPixmap(x, y, scaled_pixmap)
        
        # 绘制临时层（正在绘制的图形）
        if self.temp_pixmap and not self.temp_pixmap.isNull():
            painter.drawPixmap(0, 0, self.temp_pixmap)
        
        painter.end()
    
    def mousePressEvent(self, event: QMouseEvent):
        """鼠标按下事件"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_drawing = True
            self.last_point = event.pos()
            
            if self.current_tool == EditorTool.PEN:
                self.current_points = [event.pos()]
            elif self.current_tool in [EditorTool.RECTANGLE, EditorTool.CIRCLE, EditorTool.ARROW]:
                self.start_point = event.pos()
                self.end_point = event.pos()
            elif self.current_tool == EditorTool.TEXT:
                self.text_position = event.pos()
                # TODO: 弹出文字输入对话框
    
    def mouseMoveEvent(self, event: QMouseEvent):
        """鼠标移动事件"""
        if self.is_drawing:
            if self.current_tool == EditorTool.PEN:
                self.current_points.append(event.pos())
                self.last_point = event.pos()
                self.update_temp_pixmap()
            elif self.current_tool in [EditorTool.RECTANGLE, EditorTool.CIRCLE, EditorTool.ARROW]:
                self.end_point = event.pos()
                self.update_temp_pixmap()
    
    def mouseReleaseEvent(self, event: QMouseEvent):
        """鼠标释放事件"""
        if event.button() == Qt.MouseButton.LeftButton and self.is_drawing:
            self.is_drawing = False
            
            if self.current_tool == EditorTool.PEN:
                if len(self.current_points) >= 2:
                    # 转换为PIL坐标
                    pil_points = [(p.x(), p.y()) for p in self.current_points]
                    self.editor.draw_pen(
                        pil_points,
                        color=self.current_color.name(),
                        width=self.line_width
                    )
                self.current_points = []
            elif self.current_tool == EditorTool.RECTANGLE:
                if self.start_point and self.end_point:
                    self.editor.draw_rectangle(
                        (self.start_point.x(), self.start_point.y()),
                        (self.end_point.x(), self.end_point.y()),
                        color=self.current_color.name(),
                        width=self.line_width
                    )
            elif self.current_tool == EditorTool.CIRCLE:
                if self.start_point and self.end_point:
                    # 计算圆心和半径
                    cx = (self.start_point.x() + self.end_point.x()) // 2
                    cy = (self.start_point.y() + self.end_point.y()) // 2
                    radius = min(
                        abs(self.end_point.x() - self.start_point.x()),
                        abs(self.end_point.y() - self.start_point.y())
                    ) // 2
                    self.editor.draw_circle(
                        (cx, cy),
                        radius,
                        color=self.current_color.name(),
                        width=self.line_width
                    )
            elif self.current_tool == EditorTool.ARROW:
                if self.start_point and self.end_point:
                    self.editor.draw_arrow(
                        (self.start_point.x(), self.start_point.y()),
                        (self.end_point.x(), self.end_point.y()),
                        color=self.current_color.name(),
                        width=self.line_width
                    )
            
            self.temp_pixmap = None
            self.image_changed.emit()
            self.update()
    
    def keyPressEvent(self, event: QKeyEvent):
        """键盘事件"""
        # Ctrl+Z: 撤销
        if event.key() == Qt.Key.Key_Z and event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            self.undo()
        # Ctrl+Y: 重做
        elif event.key() == Qt.Key.Key_Y and event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            self.redo()
    
    def update_temp_pixmap(self):
        """更新临时绘制层"""
        self.temp_pixmap = QPixmap(self.size())
        self.temp_pixmap.fill(Qt.GlobalColor.transparent)
        
        painter = QPainter(self.temp_pixmap)
        pen = QPen(self.current_color, self.line_width)
        painter.setPen(pen)
        
        if self.current_tool == EditorTool.PEN and len(self.current_points) >= 2:
            for i in range(len(self.current_points) - 1):
                painter.drawLine(self.current_points[i], self.current_points[i + 1])
        
        elif self.current_tool == EditorTool.RECTANGLE and self.start_point and self.end_point:
            painter.drawRect(QRect(self.start_point, self.end_point))
        
        elif self.current_tool == EditorTool.CIRCLE and self.start_point and self.end_point:
            cx = (self.start_point.x() + self.end_point.x()) // 2
            cy = (self.start_point.y() + self.end_point.y()) // 2
            radius = min(
                abs(self.end_point.x() - self.start_point.x()),
                abs(self.end_point.y() - self.start_point.y())
            ) // 2
            painter.drawEllipse(QPoint(cx, cy), radius, radius)
        
        elif self.current_tool == EditorTool.ARROW and self.start_point and self.end_point:
            painter.drawLine(self.start_point, self.end_point)
            # TODO: 绘制箭头头部
        
        painter.end()
        self.update()
    
    def set_tool(self, tool: str):
        """设置当前工具"""
        self.current_tool = tool
    
    def set_color(self, color: QColor):
        """设置颜色"""
        self.current_color = color
    
    def set_line_width(self, width: int):
        """设置线条宽度"""
        self.line_width = width
    
    def undo(self):
        """撤销"""
        if self.editor and self.editor.undo():
            self.image_changed.emit()
            self.update()
    
    def redo(self):
        """重做"""
        if self.editor and self.editor.redo():
            self.image_changed.emit()
            self.update()
    
    def clear(self):
        """清空"""
        if self.editor:
            self.editor.clear()
            self.image_changed.emit()
            self.update()
    
    def reset(self):
        """重置"""
        if self.editor:
            self.editor.reset()
            self.image_changed.emit()
            self.update()
    
    def save(self, output_path: str):
        """保存图像"""
        if self.editor:
            self.editor.save(output_path)


class EditorWindow(QMainWindow):
    """图像编辑窗口"""
    
    # 信号
    image_saved = pyqtSignal(str)
    
    def __init__(self, image_path: Optional[str] = None, parent=None):
        super().__init__(parent)
        
        self.setWindowTitle("图像编辑器")
        self.setMinimumSize(800, 600)
        
        # 创建中央画布
        self.canvas = CanvasWidget()
        self.setCentralWidget(self.canvas)
        
        # 连接信号
        self.canvas.image_changed.connect(self.on_image_changed)
        
        # 创建工具栏
        self.create_toolbar()
        
        # 创建状态栏
        self.statusBar().showMessage("就绪")
        
        # 加载图像
        if image_path:
            self.load_image(image_path)
    
    def create_toolbar(self):
        """创建工具栏"""
        toolbar = self.addToolBar("工具")
        toolbar.setMovable(False)
        
        # 画笔工具
        pen_btn = QPushButton("画笔")
        pen_btn.setCheckable(True)
        pen_btn.setChecked(True)
        pen_btn.clicked.connect(lambda: self.set_tool(EditorTool.PEN))
        toolbar.addWidget(pen_btn)
        
        # 矩形工具
        rect_btn = QPushButton("矩形")
        rect_btn.setCheckable(True)
        rect_btn.clicked.connect(lambda: self.set_tool(EditorTool.RECTANGLE))
        toolbar.addWidget(rect_btn)
        
        # 圆形工具
        circle_btn = QPushButton("圆形")
        circle_btn.setCheckable(True)
        circle_btn.clicked.connect(lambda: self.set_tool(EditorTool.CIRCLE))
        toolbar.addWidget(circle_btn)
        
        # 箭头工具
        arrow_btn = QPushButton("箭头")
        arrow_btn.setCheckable(True)
        arrow_btn.clicked.connect(lambda: self.set_tool(EditorTool.ARROW))
        toolbar.addWidget(arrow_btn)
        
        # 文字工具
        text_btn = QPushButton("文字")
        text_btn.setCheckable(True)
        text_btn.clicked.connect(lambda: self.set_tool(EditorTool.TEXT))
        toolbar.addWidget(text_btn)
        
        toolbar.addSeparator()
        
        # 颜色选择
        self.color_btn = QPushButton()
        self.color_btn.setFixedSize(30, 30)
        self.color_btn.setStyleSheet(f"background-color: {EDITOR_DEFAULT_COLOR}; border: 1px solid black;")
        self.color_btn.clicked.connect(self.choose_color)
        toolbar.addWidget(self.color_btn)
        
        # 线条宽度
        width_label = QLabel("线宽:")
        toolbar.addWidget(width_label)
        
        self.width_spin = QSpinBox()
        self.width_spin.setRange(1, 20)
        self.width_spin.setValue(EDITOR_DEFAULT_LINE_WIDTH)
        self.width_spin.valueChanged.connect(self.set_line_width)
        toolbar.addWidget(self.width_spin)
        
        toolbar.addSeparator()
        
        # 撤销按钮
        undo_btn = QPushButton("撤销")
        undo_btn.clicked.connect(self.canvas.undo)
        toolbar.addWidget(undo_btn)
        
        # 重做按钮
        redo_btn = QPushButton("重做")
        redo_btn.clicked.connect(self.canvas.redo)
        toolbar.addWidget(redo_btn)
        
        toolbar.addSeparator()
        
        # 清空按钮
        clear_btn = QPushButton("清空")
        clear_btn.clicked.connect(self.canvas.clear)
        toolbar.addWidget(clear_btn)
        
        # 重置按钮
        reset_btn = QPushButton("重置")
        reset_btn.clicked.connect(self.canvas.reset)
        toolbar.addWidget(reset_btn)
        
        toolbar.addSeparator()
        
        # 保存按钮
        save_btn = QPushButton("保存")
        save_btn.clicked.connect(self.save_image)
        toolbar.addWidget(save_btn)
        
        # 工具按钮组
        self.tool_buttons = [pen_btn, rect_btn, circle_btn, arrow_btn, text_btn]
        for btn in self.tool_buttons:
            btn.setAutoExclusive(True)
    
    def load_image(self, image_path: str):
        """加载图像"""
        self.canvas.set_image(image_path)
        self.statusBar().showMessage(f"已加载: {image_path}")
    
    def set_tool(self, tool: str):
        """设置当前工具"""
        self.canvas.set_tool(tool)
        
        # 更新按钮状态
        for btn in self.tool_buttons:
            btn.setChecked(False)
        
        tool_index = {
            EditorTool.PEN: 0,
            EditorTool.RECTANGLE: 1,
            EditorTool.CIRCLE: 2,
            EditorTool.ARROW: 3,
            EditorTool.TEXT: 4,
        }.get(tool, 0)
        
        if tool_index < len(self.tool_buttons):
            self.tool_buttons[tool_index].setChecked(True)
    
    def choose_color(self):
        """选择颜色"""
        color = QColorDialog.getColor(self.canvas.current_color, self)
        if color.isValid():
            self.canvas.set_color(color)
            self.color_btn.setStyleSheet(f"background-color: {color.name()}; border: 1px solid black;")
    
    def set_line_width(self, width: int):
        """设置线条宽度"""
        self.canvas.set_line_width(width)
    
    def save_image(self):
        """保存图像"""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "保存图像", "", "PNG Files (*.png);;JPEG Files (*.jpg);;All Files (*)"
        )
        
        if file_path:
            self.canvas.save(file_path)
            self.image_saved.emit(file_path)
            self.statusBar().showMessage(f"已保存: {file_path}")
    
    def on_image_changed(self):
        """图像改变事件"""
        self.statusBar().showMessage("图像已修改")
