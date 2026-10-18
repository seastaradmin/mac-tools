"""
音频录音模块
"""

import pyaudio
import wave
import threading
import math
import sys
from array import array
from typing import Optional, Callable
from datetime import datetime

from config import (
    AUDIO_DIR, AUDIO_SAMPLE_RATE, AUDIO_CHANNELS, 
    AUDIO_CHUNK, AUDIO_FORMAT_BITS
)


class AudioRecorder:
    """音频录音类"""
    
    def __init__(self):
        self.audio = pyaudio.PyAudio()
        self.stream = None
        self.frames = []
        self.is_recording = False
        self.recording_thread = None
        self.output_path = None
        
        # 回调函数
        self.on_data_callback: Optional[Callable] = None
        self.on_finish_callback: Optional[Callable] = None
    
    def start_recording(self, output_path: Optional[str] = None) -> str:
        """
        开始录音
        
        Args:
            output_path: 输出文件路径，如果为None则自动生成
            
        Returns:
            输出文件路径
        """
        if self.is_recording:
            print("已经在录音中")
            return self.output_path
        
        if output_path is None:
            output_path = self._generate_filename()
        
        self.output_path = output_path
        self.frames = []
        self.stream = None
        self.recording_thread = None
        
        try:
            self.stream = self.audio.open(
                format=pyaudio.paInt16,
                channels=AUDIO_CHANNELS,
                rate=AUDIO_SAMPLE_RATE,
                input=True,
                frames_per_buffer=AUDIO_CHUNK
            )
            self.is_recording = True
            self.recording_thread = threading.Thread(target=self._record)
            self.recording_thread.daemon = True
            self.recording_thread.start()
        except Exception:
            self.is_recording = False
            self._close_stream()
            self.output_path = None
            self.frames = []
            self.recording_thread = None
            raise
        
        return output_path
    
    def stop_recording(self) -> Optional[str]:
        """
        停止录音
        
        Returns:
            录音文件路径
        """
        if not self.is_recording and not self.stream:
            print("没有在录音")
            return None
        
        self.is_recording = False
        
        # 等待录音线程结束
        if self.recording_thread:
            self.recording_thread.join(timeout=1.0)
        
        self._close_stream()
        self.recording_thread = None
        
        # 保存录音文件
        if self.frames:
            self._save_wav()
            if self.on_finish_callback:
                self.on_finish_callback(self.output_path)
            return self.output_path
        
        return None

    def _close_stream(self):
        stream = getattr(self, "stream", None)
        if not stream:
            return
        try:
            if stream.is_active():
                stream.stop_stream()
        except Exception:
            pass
        try:
            stream.close()
        finally:
            self.stream = None
    
    def _record(self):
        """录音线程函数"""
        while self.is_recording:
            try:
                data = self.stream.read(AUDIO_CHUNK, exception_on_overflow=False)
                self.frames.append(data)
                
                # 调用数据回调
                if self.on_data_callback:
                    self.on_data_callback(data)
                    
            except Exception as e:
                print(f"录音错误: {e}")
                break
        self.is_recording = False
    
    def _save_wav(self):
        """保存WAV文件"""
        wf = wave.open(self.output_path, 'wb')
        wf.setnchannels(AUDIO_CHANNELS)
        wf.setsampwidth(self.audio.get_sample_size(pyaudio.paInt16))
        wf.setframerate(AUDIO_SAMPLE_RATE)
        wf.writeframes(b''.join(self.frames))
        wf.close()
    
    def _generate_filename(self) -> str:
        """生成录音文件名"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"recording_{timestamp}.wav"
        return str(AUDIO_DIR / filename)
    
    def get_audio_level(self) -> float:
        """
        获取当前音频电平（用于可视化）
        
        Returns:
            音频电平值 (0.0 - 1.0)
        """
        if not self.frames:
            return 0.0
        
        # 获取最后一帧数据
        last_frame = self.frames[-1]
        if not last_frame:
            return 0.0

        audio_data = array('h')
        audio_data.frombytes(last_frame)
        if sys.byteorder == "big":
            audio_data.byteswap()
        if not audio_data:
            return 0.0
        
        # 计算RMS电平
        square_sum = sum(sample * sample for sample in audio_data)
        rms = math.sqrt(square_sum / len(audio_data))
        
        # 归一化到0-1
        max_value = 32768.0  # 16位音频的最大值
        level = min(rms / max_value, 1.0)
        
        return level
    
    def set_on_data_callback(self, callback: Callable):
        """设置数据回调"""
        self.on_data_callback = callback
    
    def set_on_finish_callback(self, callback: Callable):
        """设置完成回调"""
        self.on_finish_callback = callback
    
    def __del__(self):
        """析构函数"""
        self.close()

    def close(self):
        """释放录音资源。"""
        if getattr(self, "is_recording", False):
            self.stop_recording()
        else:
            self._close_stream()
        recording_thread = getattr(self, "recording_thread", None)
        if recording_thread and recording_thread.is_alive():
            self.recording_thread.join(timeout=1.0)
        self.recording_thread = None
        try:
            audio = getattr(self, "audio", None)
            if audio:
                audio.terminate()
        except Exception:
            pass


class AudioVisualizer:
    """音频可视化类"""
    
    def __init__(self, max_points: int = 100):
        self.max_points = max_points
        self.levels = []
    
    def add_level(self, level: float):
        """添加音频电平"""
        self.levels.append(level)
        if len(self.levels) > self.max_points:
            self.levels.pop(0)
    
    def get_levels(self) -> list:
        """获取电平历史"""
        return self.levels.copy()
    
    def clear(self):
        """清空历史"""
        self.levels.clear()
