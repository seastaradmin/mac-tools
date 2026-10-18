"""
截图功能模块 - 调用macOS screencapture命令
"""

import subprocess
import os
import time
from pathlib import Path
from typing import Optional, Tuple
from datetime import datetime

from config import SCREENSHOT_DIR


class ScreenCaptureError(RuntimeError):
    """Raised when the system screenshot command fails."""


class ScreenCapture:
    """屏幕截图类"""
    
    def __init__(self):
        self.screenshot_dir = SCREENSHOT_DIR
        
    def capture_full_screen(self, output_path: Optional[str] = None) -> str:
        """
        全屏截图
        
        Args:
            output_path: 输出文件路径，如果为None则自动生成
            
        Returns:
            截图文件路径
        """
        if output_path is None:
            output_path = self._generate_filename("fullscreen")
        
        cmd = ["screencapture", "-x", output_path]
        self._run_command(cmd)
        return output_path
    
    def capture_interactive(self, output_path: Optional[str] = None) -> str:
        """
        交互式截图（用户手动选择区域）
        
        Args:
            output_path: 输出文件路径，如果为None则自动生成
            
        Returns:
            截图文件路径
        """
        if output_path is None:
            output_path = self._generate_filename("interactive")
        
        # -i 交互模式，-x 不播放快门声
        cmd = ["screencapture", "-i", "-x", output_path]
        result = self._run_command(cmd, check=False)
        
        # 检查文件是否生成（用户可能取消了截图）
        if os.path.exists(output_path):
            return output_path
        if result.returncode != 0 and (result.stderr or result.stdout):
            raise ScreenCaptureError((result.stderr or result.stdout).strip())
        return None
    
    def capture_window(self, output_path: Optional[str] = None) -> str:
        """
        窗口截图
        
        Args:
            output_path: 输出文件路径，如果为None则自动生成
            
        Returns:
            截图文件路径
        """
        if output_path is None:
            output_path = self._generate_filename("window")
        
        # -w 窗口模式，-x 不播放快门声
        cmd = ["screencapture", "-w", "-x", output_path]
        self._run_command(cmd)
        return output_path
    
    def capture_region(self, x: int, y: int, width: int, height: int, 
                       output_path: Optional[str] = None) -> str:
        """
        区域截图
        
        Args:
            x: 区域左上角x坐标
            y: 区域左上角y坐标
            width: 区域宽度
            height: 区域高度
            output_path: 输出文件路径，如果为None则自动生成
            
        Returns:
            截图文件路径
        """
        if output_path is None:
            output_path = self._generate_filename("region")
        
        # -R 指定区域
        region = f"{x},{y},{width},{height}"
        cmd = ["screencapture", "-R", region, "-x", output_path]
        self._run_command(cmd)
        return output_path
    
    def capture_with_delay(self, delay_seconds: int = 3, 
                          output_path: Optional[str] = None) -> str:
        """
        延时截图
        
        Args:
            delay_seconds: 延时秒数
            output_path: 输出文件路径，如果为None则自动生成
            
        Returns:
            截图文件路径
        """
        if output_path is None:
            output_path = self._generate_filename("delayed")
        
        # -T 延时秒数
        cmd = ["screencapture", "-T", str(delay_seconds), "-x", output_path]
        self._run_command(cmd)
        return output_path
    
    def _run_command(self, cmd: list, check: bool = True):
        """执行系统命令"""
        try:
            result = subprocess.run(cmd, check=False, capture_output=True, text=True)
            if check and result.returncode != 0:
                raise ScreenCaptureError((result.stderr or result.stdout).strip())
            return result
        except subprocess.CalledProcessError as e:
            print(f"截图命令执行失败: {e}")
            raise
        except FileNotFoundError:
            print("未找到screencapture命令，请确认在macOS系统上运行")
            raise
    
    def _generate_filename(self, prefix: str = "screenshot") -> str:
        """生成截图文件名"""
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{prefix}_{timestamp}.png"
        return str(self.screenshot_dir / filename)
    
    def get_latest_screenshot(self) -> Optional[str]:
        """获取最新的截图文件"""
        screenshots = list(self.screenshot_dir.glob("*.png"))
        if not screenshots:
            return None
        return str(max(screenshots, key=os.path.getmtime))
    
    def list_screenshots(self) -> list:
        """列出所有截图文件"""
        screenshots = list(self.screenshot_dir.glob("*.png"))
        return sorted(screenshots, key=os.path.getmtime, reverse=True)
