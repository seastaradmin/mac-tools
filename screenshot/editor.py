"""
图像编辑器模块 - 提供图画编辑功能
"""

from typing import Optional, List, Tuple
from PIL import Image, ImageDraw, ImageFont
import json
from pathlib import Path

from config import EditorTool


class DrawAction:
    """绘制动作类"""
    
    def __init__(self, tool: str, points: list, color: str, width: int, **kwargs):
        self.tool = tool
        self.points = points
        self.color = color
        self.width = width
        self.extra = kwargs
    
    def to_dict(self) -> dict:
        return {
            "tool": self.tool,
            "points": self.points,
            "color": self.color,
            "width": self.width,
            **self.extra
        }


class ImageEditor:
    """图像编辑器类"""
    
    def __init__(self, image_path: Optional[str] = None):
        """
        初始化编辑器
        
        Args:
            image_path: 图片路径，如果为None则创建空白画布
        """
        if image_path:
            self.original_image = Image.open(image_path)
            self.image = self.original_image.copy()
        else:
            self.original_image = None
            self.image = Image.new("RGB", (800, 600), "white")
        
        self.draw = ImageDraw.Draw(self.image)
        self.actions: List[DrawAction] = []
        self.undo_stack: List[Image.Image] = []
        self.redo_stack: List[Image.Image] = []
        
        # 保存初始状态用于撤销
        self._save_state()
    
    def _save_state(self):
        """保存当前图像状态"""
        self.undo_stack.append(self.image.copy())
        self.redo_stack.clear()
    
    def undo(self) -> bool:
        """
        撤销操作
        
        Returns:
            是否成功撤销
        """
        if len(self.undo_stack) > 1:
            self.redo_stack.append(self.undo_stack.pop())
            self.image = self.undo_stack[-1].copy()
            self.draw = ImageDraw.Draw(self.image)
            return True
        return False
    
    def redo(self) -> bool:
        """
        重做操作
        
        Returns:
            是否成功重做
        """
        if self.redo_stack:
            state = self.redo_stack.pop()
            self.undo_stack.append(state)
            self.image = state.copy()
            self.draw = ImageDraw.Draw(self.image)
            return True
        return False
    
    def draw_pen(self, points: List[Tuple[int, int]], color: str = "#FF0000", 
                 width: int = 3):
        """
        画笔工具
        
        Args:
            points: 点列表
            color: 颜色
            width: 线条宽度
        """
        if len(points) < 2:
            return
        
        self._save_state()
        
        # 绘制线条
        for i in range(len(points) - 1):
            self.draw.line([points[i], points[i + 1]], fill=color, width=width)
        
        # 记录动作
        self.actions.append(DrawAction(EditorTool.PEN, points, color, width))
    
    def draw_rectangle(self, start: Tuple[int, int], end: Tuple[int, int], 
                      color: str = "#FF0000", width: int = 3, fill: bool = False):
        """
        矩形工具
        
        Args:
            start: 起始点
            end: 结束点
            color: 颜色
            width: 线条宽度
            fill: 是否填充
        """
        self._save_state()
        
        # 绘制矩形
        if fill:
            self.draw.rectangle([start, end], fill=color)
        else:
            self.draw.rectangle([start, end], outline=color, width=width)
        
        # 记录动作
        self.actions.append(DrawAction(
            EditorTool.RECTANGLE, [start, end], color, width, fill=fill
        ))
    
    def draw_circle(self, center: Tuple[int, int], radius: int, 
                   color: str = "#FF0000", width: int = 3, fill: bool = False):
        """
        圆形工具
        
        Args:
            center: 圆心
            radius: 半径
            color: 颜色
            width: 线条宽度
            fill: 是否填充
        """
        self._save_state()
        
        # 计算边界框
        x, y = center
        bbox = [x - radius, y - radius, x + radius, y + radius]
        
        # 绘制圆形
        if fill:
            self.draw.ellipse(bbox, fill=color)
        else:
            self.draw.ellipse(bbox, outline=color, width=width)
        
        # 记录动作
        self.actions.append(DrawAction(
            EditorTool.CIRCLE, [center, (radius, radius)], color, width, fill=fill
        ))
    
    def draw_arrow(self, start: Tuple[int, int], end: Tuple[int, int], 
                  color: str = "#FF0000", width: int = 3):
        """
        箭头工具
        
        Args:
            start: 起始点
            end: 结束点
            color: 颜色
            width: 线条宽度
        """
        self._save_state()
        
        # 绘制主线
        self.draw.line([start, end], fill=color, width=width)
        
        # 计算箭头
        import math
        dx = end[0] - start[0]
        dy = end[1] - start[1]
        angle = math.atan2(dy, dx)
        
        # 箭头长度
        arrow_length = 15
        arrow_angle = math.pi / 6  # 30度
        
        # 计算箭头两个点
        x1 = end[0] - arrow_length * math.cos(angle - arrow_angle)
        y1 = end[1] - arrow_length * math.sin(angle - arrow_angle)
        x2 = end[0] - arrow_length * math.cos(angle + arrow_angle)
        y2 = end[1] - arrow_length * math.sin(angle + arrow_angle)
        
        # 绘制箭头
        self.draw.line([end, (x1, y1)], fill=color, width=width)
        self.draw.line([end, (x2, y2)], fill=color, width=width)
        
        # 记录动作
        self.actions.append(DrawAction(
            EditorTool.ARROW, [start, end], color, width
        ))
    
    def draw_text(self, position: Tuple[int, int], text: str, 
                 color: str = "#FF0000", font_size: int = 20):
        """
        文字工具
        
        Args:
            position: 位置
            text: 文字内容
            color: 颜色
            font_size: 字体大小
        """
        self._save_state()
        
        # 尝试加载系统字体
        try:
            font = ImageFont.truetype("/System/Library/Fonts/PingFang.ttc", font_size)
        except:
            font = ImageFont.load_default()
        
        # 绘制文字
        self.draw.text(position, text, fill=color, font=font)
        
        # 记录动作
        self.actions.append(DrawAction(
            EditorTool.TEXT, [position], color, font_size, text=text
        ))
    
    def clear(self):
        """清空画布"""
        self._save_state()
        self.image = Image.new("RGB", self.image.size, "white")
        self.draw = ImageDraw.Draw(self.image)
        self.actions.clear()
    
    def reset(self):
        """重置为原始图像"""
        if self.original_image:
            self._save_state()
            self.image = self.original_image.copy()
            self.draw = ImageDraw.Draw(self.image)
            self.actions.clear()
    
    def save(self, output_path: str, format: str = "PNG"):
        """
        保存图像
        
        Args:
            output_path: 输出路径
            format: 图像格式
        """
        self.image.save(output_path, format=format)
    
    def get_image(self) -> Image.Image:
        """获取当前图像"""
        return self.image
    
    def get_size(self) -> Tuple[int, int]:
        """获取图像尺寸"""
        return self.image.size
    
    def resize(self, width: int, height: int):
        """调整图像大小"""
        self._save_state()
        self.image = self.image.resize((width, height), Image.Resampling.LANCZOS)
        self.draw = ImageDraw.Draw(self.image)
    
    def crop(self, box: Tuple[int, int, int, int]):
        """
        裁剪图像
        
        Args:
            box: 裁剪区域 (left, top, right, bottom)
        """
        self._save_state()
        self.image = self.image.crop(box)
        self.draw = ImageDraw.Draw(self.image)
    
    def to_base64(self) -> str:
        """将图像转换为base64字符串"""
        import io
        import base64
        
        buffer = io.BytesIO()
        self.image.save(buffer, format="PNG")
        return base64.b64encode(buffer.getvalue()).decode()
