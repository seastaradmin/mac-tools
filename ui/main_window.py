"""
主窗口 — Apple 风格极简 + 系统托盘常驻
纯白通透 · 流式识别 · 浮动录音指示器 · 线程安全
"""

import os
import subprocess
import traceback
from typing import List
from AppKit import NSWorkspace
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QApplication,
    QFrame, QDialog, QMessageBox, QGraphicsDropShadowEffect,
    QSystemTrayIcon, QMenu, QWidgetAction
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QThread, QObject, QRectF, QPoint
from PyQt6.QtGui import (
    QFont, QPixmap, QColor, QIcon, QAction, QPainter, QPen, QBrush,
    QLinearGradient, QRadialGradient, QCursor, QPolygon
)

from clipboard_history.service import ClipboardHistoryService
from clipboard_history.store import ClipboardHistoryStore
from speech.recorder import AudioRecorder
from speech.recognizer import SpeechRecognizer
from app_diagnostics import collect_diagnostics, format_diagnostics_report
from app_diagnostics import is_screen_recording_trusted
from hotkeys.manager import HotkeyManager, is_accessibility_trusted
from macos_permissions import (
    is_input_monitoring_trusted,
    open_privacy_settings,
    prompt_accessibility_permission,
    prompt_input_monitoring_permission,
    prompt_screen_recording_permission,
)
from ui.pin_window import PinWindow
from ui.clipboard_history_dialog import ClipboardHistoryMenuContent
from ui.screenshot_overlay import ScreenshotOverlay
from ui.settings_dialog import SettingsDialog
from ui.window_levels import keep_window_on_top
from ui.styles import (
    COLORS, SIZES, GLOBAL_STYLESHEET,
    ghost_button_style, hotkey_badge_style
)
from config import (
    CLIPBOARD_HISTORY_FILE, DEFAULT_CLIPBOARD_HISTORY_LIMIT,
    DEFAULT_CLIPBOARD_TEXT_MAX_LENGTH, MIMO_API_KEY, load_user_config, DEFAULT_HOTKEYS
)
from voice_input import type_text


# ═══════════════════════════════════════════════════════════
#  线程安全桥 — 从非 GUI 线程安全调用 GUI
# ═══════════════════════════════════════════════════════════

class ThreadSafeBridge(QObject):
    """将后台线程的调用安全转发到 GUI 主线程"""
    screenshot_requested = pyqtSignal()
    clipboard_history_requested = pyqtSignal()
    voice_toggle_requested = pyqtSignal()
    voice_press = pyqtSignal()    # 长按按下 — 开始录音
    voice_release = pyqtSignal()  # 长按释放 — 停止录音


# ═══════════════════════════════════════════════════════════
#  线程
# ═══════════════════════════════════════════════════════════

class SimpleRecognitionThread(QThread):
    """简单的语音识别线程 — 非流式，稳定可靠"""
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, recognizer, audio_path, language="zh"):
        super().__init__()
        self.recognizer = recognizer
        self.audio_path = audio_path
        self.language = language

    def run(self):
        try:
            result = self.recognizer.recognize_file(self.audio_path, self.language)
            if result:
                self.finished.emit(result)
            else:
                self.error.emit(self.recognizer.get_last_error() or "语音识别返回空结果")
        except Exception as e:
            self.error.emit(str(e))


# ═══════════════════════════════════════════════════════════
#  阴影辅助
# ═══════════════════════════════════════════════════════════

def add_shadow(widget, blur=24, opacity=0.04, y_offset=1):
    shadow = QGraphicsDropShadowEffect(widget)
    shadow.setBlurRadius(blur)
    shadow.setColor(QColor(0, 0, 0, int(255 * opacity)))
    shadow.setOffset(0, y_offset)
    widget.setGraphicsEffect(shadow)
    return shadow


# ═══════════════════════════════════════════════════════════
#  浮动录音指示器
# ═══════════════════════════════════════════════════════════

class RecordingIndicator(QWidget):
    clicked = pyqtSignal()
    stop_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Window
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)  # show时不激活
        self._collapsed_size = 64
        self._expanded_width = 360
        self._expanded_height = 84
        self.setFixedSize(self._collapsed_size, self._collapsed_size)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self._pulse_phase = 0
        self._pulse_timer = QTimer(self)
        self._pulse_timer.timeout.connect(self._pulse_tick)
        self._auto_hide_timer = QTimer(self)
        self._auto_hide_timer.setSingleShot(True)
        self._auto_hide_timer.timeout.connect(self.show_idle)
        self._time_text = "00:00"
        self._status_text = ""
        self._state = "idle"
        self._opacity = 0.0
        self._audio_level = 0.0
        self._bars = [0.16, 0.36, 0.58, 0.42, 0.24, 0.34, 0.52, 0.28]
        self._expanded = False
        self._listening = False
        self._dragging = False
        self._drag_offset = QPoint()
        self._pressed_pos = QPoint()

    def _default_position(self):
        screen = QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()
        geometry = screen.availableGeometry()
        width = self._expanded_width if self._expanded else self._collapsed_size
        x = geometry.x() + max(0, (geometry.width() - width) // 2)
        y = geometry.y() + 8
        return x, y

    def show_idle(self):
        self._auto_hide_timer.stop()
        self._state = "idle"
        self._status_text = ""
        self._listening = False
        self._expanded = False
        self._opacity = 1.0
        self._audio_level = 0.0
        self._pulse_timer.stop()
        self._apply_size()
        self.move(*self._default_position())
        self.hide()
        self.update()

    def start(self):
        self._auto_hide_timer.stop()
        self._state = "recording"
        self._status_text = "正在录音"
        self._listening = True
        self._expanded = True
        self._apply_size()
        x, y = self._default_position()
        self.move(x, y)
        self._opacity = 1.0
        self._pulse_phase = 0
        self._audio_level = 0.0
        self._pulse_timer.start(40)
        self.show()  # show 但不激活（WA_ShowWithoutActivating 生效）
        QTimer.singleShot(0, self._apply_native_window_behavior)

    def show_transcribing(self):
        self._auto_hide_timer.stop()
        self._state = "transcribing"
        self._status_text = "识别中..."
        self._listening = False
        self._expanded = True
        self._audio_level = 0.0
        self._apply_size()
        self.move(*self._default_position())
        self._pulse_timer.start(40)
        self.show()
        QTimer.singleShot(0, self._apply_native_window_behavior)
        self.update()

    def show_done(self, message: str):
        self._state = "done"
        self._status_text = message
        self._listening = False
        self._expanded = True
        self._audio_level = 0.0
        self._apply_size()
        self.move(*self._default_position())
        self.show()
        QTimer.singleShot(0, self._apply_native_window_behavior)
        self._auto_hide_timer.start(1600)
        self.update()

    def show_error(self, message: str):
        self._state = "error"
        self._status_text = message
        self._listening = False
        self._expanded = True
        self._audio_level = 0.0
        self._apply_size()
        self.move(*self._default_position())
        self.show()
        QTimer.singleShot(0, self._apply_native_window_behavior)
        self._auto_hide_timer.start(4200)
        self.update()

    def stop(self):
        self._auto_hide_timer.stop()
        self._state = "idle"
        self._status_text = ""
        self._listening = False
        self._audio_level = 0.0
        self._pulse_timer.stop()
        self._apply_size()
        self.hide()
        self.update()

    def _apply_native_window_behavior(self):
        """macOS 原生浮窗层级：常驻、跨 Space、不激活输入焦点。"""
        keep_window_on_top(self, non_activating=True)

    def set_time(self, text: str):
        self._time_text = text
        self.update()

    def set_audio_level(self, level: float):
        self._audio_level = max(0.0, min(float(level), 1.0))
        self.update()

    def _apply_size(self):
        right = self.geometry().right()
        top = self.geometry().top()
        if self._expanded:
            self.setFixedSize(self._expanded_width, self._expanded_height)
        else:
            self.setFixedSize(self._collapsed_size, self._collapsed_size)
        if right > 0:
            self.move(right - self.width() + 1, top)

    def _pulse_tick(self):
        import math
        self._pulse_phase = (self._pulse_phase + 1) % 50
        if self._opacity < 1.0:
            self._opacity = min(1.0, self._opacity + 0.08)
        for i in range(len(self._bars)):
            wave = 0.5 + 0.5 * math.sin(self._pulse_phase * 0.32 + i * 0.95)
            if self._state == "recording":
                target = 0.18 + wave * 0.34 + self._audio_level * (0.42 + i * 0.035)
            elif self._state == "transcribing":
                target = 0.20 + wave * 0.26
            else:
                target = 0.18
            self._bars[i] = self._bars[i] * 0.68 + min(target, 1.0) * 0.32
        self.update()

    def paintEvent(self, event):
        import math
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setOpacity(self._opacity)

        if self._expanded:
            self._paint_console(painter)
        else:
            self._paint_ball(painter)

        painter.end()

    def _paint_ball(self, painter):
        import math
        pulse = 0.5 + 0.5 * math.sin(self._pulse_phase * 0.22)
        level = min(1.0, self._audio_level * 1.7 + pulse * 0.18) if self._listening else 0.0

        glow = QRadialGradient(QRectF(0, 0, 64, 64).center(), 34 + pulse * 8)
        glow.setColorAt(0.0, QColor(214, 58, 44, int(52 + level * 128)))
        glow.setColorAt(0.58, QColor(128, 45, 36, int(30 + level * 64)))
        glow.setColorAt(1.0, QColor(10, 14, 24, 0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(glow)
        painter.drawEllipse(QRectF(0, 0, 64, 64))

        ball = QRectF(7, 7, 50, 50)
        bg = QRadialGradient(ball.center(), 36)
        bg.setColorAt(0.0, QColor(23, 37, 55, 246))
        bg.setColorAt(0.68, QColor(12, 18, 31, 242))
        bg.setColorAt(1.0, QColor(7, 11, 20, 244))
        painter.setBrush(bg)
        painter.drawEllipse(ball)

        painter.setPen(QPen(QColor(112, 137, 184, 76), 1.1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(ball.adjusted(0.6, 0.6, -0.6, -0.6))

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(214, 58, 44, 220) if self._listening else QColor(126, 148, 184, 190))
        for i, bar in enumerate(self._bars[:3]):
            h = 8 + bar * 14
            x = 23 + i * 7
            painter.drawRoundedRect(QRectF(x, 32 - h / 2, 4, h), 2, 2)

    def _paint_console(self, painter):
        import math

        panel = QRectF(2, 2, self.width() - 4, self.height() - 6)
        bg = QLinearGradient(0, panel.top(), 0, panel.bottom())
        bg.setColorAt(0.0, QColor(36, 28, 22, 246))
        bg.setColorAt(1.0, QColor(10, 8, 7, 244))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(bg)
        painter.drawRoundedRect(panel, 22, 22)

        edge = QLinearGradient(0, panel.top(), 0, panel.bottom())
        edge.setColorAt(0.0, QColor(255, 255, 255, 46))
        edge.setColorAt(1.0, QColor(0, 0, 0, 54))
        painter.setPen(QPen(QBrush(edge), 1.2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(panel.adjusted(0.6, 0.6, -0.6, -0.6), 21, 21)

        state_color = {
            "recording": QColor(214, 58, 44, 235),
            "transcribing": QColor(192, 110, 63, 235),
            "done": QColor(83, 154, 108, 235),
            "error": QColor(197, 86, 63, 235),
        }.get(self._state, QColor(126, 148, 184, 190))

        if self._state == "transcribing":
            spinner = QRectF(18, 25, 28, 28)
            painter.setPen(QPen(QColor(255, 255, 255, 68), 3))
            painter.drawEllipse(spinner)
            painter.setPen(QPen(state_color, 3))
            painter.drawArc(spinner, int((self._pulse_phase * 11) % 360) * 16, 250 * 16)
        else:
            pulse = 0.5 + 0.5 * math.sin(self._pulse_phase * 0.22)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(state_color.red(), state_color.green(), state_color.blue(), 54 + int(pulse * 50)))
            painter.drawEllipse(QRectF(12, 17, 42, 42))
            painter.setBrush(state_color)
            painter.drawEllipse(QRectF(23, 28, 20, 20))
            painter.setBrush(QColor(255, 255, 255, 235))
            if self._state == "done":
                painter.setPen(QPen(QColor(255, 255, 255, 235), 2.4))
                painter.drawLine(28, 39, 34, 45)
                painter.drawLine(34, 45, 44, 32)
                painter.setPen(Qt.PenStyle.NoPen)
            elif self._state == "error":
                font = QFont("Menlo", 14, QFont.Weight.Bold)
                painter.setFont(font)
                painter.drawText(QRectF(23, 27, 20, 20), Qt.AlignmentFlag.AlignCenter, "!")
            elif self._state == "recording":
                painter.drawRoundedRect(QRectF(30, 35, 6, 6), 3, 3)

        dot_x = 74
        dot_y = 61
        for i, level in enumerate(self._bars):
            height = 6 + level * 14
            width = 4
            alpha = 150 + int(level * 92)
            color = QColor(state_color.red(), state_color.green(), state_color.blue(), alpha)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(color)
            painter.drawRoundedRect(
                QRectF(dot_x + i * 8, dot_y - height / 2, width, height),
                2, 2
            )

        painter.setPen(QColor(255, 255, 255, 230))
        font = QFont("PingFang SC", 15, QFont.Weight.DemiBold)
        painter.setFont(font)
        painter.drawText(
            74, 17, 148, 24,
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            self._status_text or "正在录音"
        )

        painter.setPen(QColor(206, 218, 240, 132))
        font = QFont("Menlo", 11, QFont.Weight.Medium)
        painter.setFont(font)
        painter.drawText(
            222, 18, 54, 20,
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
            self._time_text if self._state == "recording" else ""
        )

        stop_rect = QRectF(self.width() - 58, 22, 40, 40)
        if self._state == "recording":
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(255, 255, 255, 36))
            painter.drawRoundedRect(stop_rect, 20, 20)
            painter.setBrush(QColor(255, 255, 255, 232))
            painter.drawRoundedRect(
                QRectF(stop_rect.center().x() - 5, stop_rect.center().y() - 5, 10, 10),
                2, 2
            )

    def mousePressEvent(self, event):
        self._pressed_pos = event.globalPosition().toPoint()
        self._drag_offset = self._pressed_pos - self.frameGeometry().topLeft()
        self._dragging = False

    def mouseMoveEvent(self, event):
        delta = event.globalPosition().toPoint() - self._pressed_pos
        if delta.manhattanLength() > 6:
            self._dragging = True
            self.move(event.globalPosition().toPoint() - self._drag_offset)

    def mouseReleaseEvent(self, event):
        if self._dragging:
            return
        pos = event.position()
        stop_rect = QRectF(self.width() - 58, 22, 40, 40)
        if self._state == "recording" and self._expanded and stop_rect.contains(pos):
            self.stop_requested.emit()
            return
        if self._state in ("transcribing", "done", "error"):
            if self._state in ("done", "error"):
                self.show_idle()
            return
        self._expanded = not self._expanded
        self._apply_size()
        self.update()


class NativeVoiceBall(QObject):
    """macOS 原生常驻小球：NSPanel 承载，避免 Qt Tool 窗口不上屏。"""
    stop_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._panel = None
        self._view = None
        self._expanded = False
        self._listening = False
        self._time_text = "00:00"
        self._status_text = ""
        self._state = "idle"
        self._audio_level = 0.0
        self._pulse_phase = 0
        self._bars = [0.18, 0.18, 0.18, 0.18, 0.18, 0.18, 0.18, 0.18]
        self._collapsed_size = 64
        self._expanded_width = 360
        self._expanded_height = 84
        self._pulse_timer = QTimer(self)
        self._pulse_timer.timeout.connect(self._pulse_tick)
        self._auto_hide_timer = QTimer(self)
        self._auto_hide_timer.setSingleShot(True)
        self._auto_hide_timer.timeout.connect(self.show_idle)

    def show_idle(self):
        self._auto_hide_timer.stop()
        self._state = "idle"
        self._status_text = ""
        self._listening = False
        self._expanded = False
        self._audio_level = 0.0
        self._pulse_timer.stop()
        if self._panel is not None:
            self._resize_panel()
            self._panel.orderOut_(None)
        self._redraw()

    def start(self):
        self._ensure_panel()
        self._auto_hide_timer.stop()
        self._state = "recording"
        self._status_text = "正在录音"
        self._listening = True
        self._expanded = True
        self._audio_level = 0.0
        self._pulse_phase = 0
        self._resize_panel()
        self._move_to_default_position()
        self._panel.orderFrontRegardless()
        self._pulse_timer.start(40)
        self._redraw()

    def show_transcribing(self):
        self._ensure_panel()
        self._auto_hide_timer.stop()
        self._state = "transcribing"
        self._status_text = "识别中..."
        self._listening = False
        self._expanded = True
        self._audio_level = 0.0
        self._resize_panel()
        self._move_to_default_position()
        self._panel.orderFrontRegardless()
        self._pulse_timer.start(40)
        self._redraw()

    def show_done(self, message: str):
        self._ensure_panel()
        self._state = "done"
        self._status_text = message
        self._listening = False
        self._expanded = True
        self._audio_level = 0.0
        self._resize_panel()
        self._move_to_default_position()
        self._panel.orderFrontRegardless()
        self._auto_hide_timer.start(1600)
        self._redraw()

    def show_error(self, message: str):
        self._ensure_panel()
        self._state = "error"
        self._status_text = message
        self._listening = False
        self._expanded = True
        self._audio_level = 0.0
        self._resize_panel()
        self._move_to_default_position()
        self._panel.orderFrontRegardless()
        self._auto_hide_timer.start(4200)
        self._redraw()

    def stop(self):
        self._auto_hide_timer.stop()
        self._state = "idle"
        self._status_text = ""
        self._listening = False
        self._audio_level = 0.0
        self._pulse_timer.stop()
        if self._panel is not None:
            self._panel.orderOut_(None)
        self._redraw()

    def close(self):
        self._auto_hide_timer.stop()
        self._pulse_timer.stop()
        if self._panel is not None:
            self._panel.orderOut_(None)

    def set_time(self, text: str):
        self._time_text = text
        self._redraw()

    def set_audio_level(self, level: float):
        self._audio_level = max(0.0, min(float(level), 1.0))

    def _ensure_panel(self):
        if self._panel is not None:
            return
        from AppKit import (
            NSBackingStoreBuffered, NSColor, NSFloatingWindowLevel, NSMakeRect,
            NSPanel, NSScreen, NSWindowCollectionBehaviorCanJoinAllSpaces,
            NSWindowCollectionBehaviorFullScreenAuxiliary,
            NSWindowCollectionBehaviorStationary, NSWindowStyleMaskBorderless,
            NSWindowStyleMaskNonactivatingPanel,
        )

        style = NSWindowStyleMaskBorderless | NSWindowStyleMaskNonactivatingPanel
        rect = NSMakeRect(0, 0, self._collapsed_size, self._collapsed_size)
        self._panel = NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
            rect, style, NSBackingStoreBuffered, False
        )
        self._panel.setOpaque_(False)
        self._panel.setBackgroundColor_(NSColor.clearColor())
        self._panel.setHasShadow_(False)
        self._panel.setHidesOnDeactivate_(False)
        self._panel.setFloatingPanel_(True)
        self._panel.setLevel_(NSFloatingWindowLevel)
        self._panel.setCollectionBehavior_(
            NSWindowCollectionBehaviorCanJoinAllSpaces
            | NSWindowCollectionBehaviorFullScreenAuxiliary
            | NSWindowCollectionBehaviorStationary
        )
        self._panel.setReleasedWhenClosed_(False)
        if hasattr(self._panel, "setCanHide_"):
            self._panel.setCanHide_(False)

        self._view = _NativeVoiceBallView.alloc().initWithController_(self)
        self._panel.setContentView_(self._view)

        # Touch NSScreen here so PyInstaller keeps AppKit screen symbols reachable.
        _ = NSScreen.mainScreen()

    def _move_to_default_position(self):
        from AppKit import NSScreen, NSMakePoint

        screen = NSScreen.mainScreen()
        frame = screen.visibleFrame()
        width = self._expanded_width if self._expanded else self._collapsed_size
        height = self._expanded_height if self._expanded else self._collapsed_size
        x = frame.origin.x + (frame.size.width - width) / 2
        y = frame.origin.y + frame.size.height - height - 8
        self._panel.setFrameOrigin_(NSMakePoint(x, y))

    def _resize_panel(self):
        from AppKit import NSMakeRect

        width = self._expanded_width if self._expanded else self._collapsed_size
        height = self._expanded_height if self._expanded else self._collapsed_size
        frame = self._panel.frame()
        self._panel.setFrame_display_(
            NSMakeRect(frame.origin.x + frame.size.width - width, frame.origin.y, width, height),
            True
        )

    def _toggle_expanded(self):
        self._expanded = not self._expanded
        self._resize_panel()
        self._redraw()

    def _handle_primary_action(self):
        self.stop_requested.emit()

    def _pulse_tick(self):
        import math

        self._pulse_phase = (self._pulse_phase + 1) % 50
        for i in range(len(self._bars)):
            wave = 0.5 + 0.5 * math.sin(self._pulse_phase * 0.32 + i * 0.95)
            if self._state == "recording":
                target = 0.18 + wave * 0.34 + self._audio_level * (0.42 + i * 0.035)
            elif self._state == "transcribing":
                target = 0.20 + wave * 0.26
            else:
                target = 0.18
            self._bars[i] = self._bars[i] * 0.68 + min(target, 1.0) * 0.32
        self._redraw()

    def _redraw(self):
        if self._view is not None:
            self._view.setNeedsDisplay_(True)


try:
    import objc
    from AppKit import NSView

    class _NativeVoiceBallView(NSView):
        def initWithController_(self, controller):
            self = objc.super(_NativeVoiceBallView, self).init()
            if self is None:
                return None
            self._controller = controller
            self._drag_start = None
            self._frame_start = None
            return self

        def isFlipped(self):
            return True

        def acceptsFirstMouse_(self, event):
            return True

        def mouseDown_(self, event):
            self._drag_start = event.locationInWindow()
            self._frame_start = self.window().frame()

        def mouseDragged_(self, event):
            if self._drag_start is None or self._frame_start is None:
                return
            from AppKit import NSMakePoint
            current = event.locationInWindow()
            dx = current.x - self._drag_start.x
            dy = current.y - self._drag_start.y
            self.window().setFrameOrigin_(
                NSMakePoint(self._frame_start.origin.x + dx, self._frame_start.origin.y + dy)
            )

        def mouseUp_(self, event):
            controller = self._controller
            point = event.locationInWindow()
            if controller._expanded and 188 <= point.x <= 232 and 27 <= point.y <= 71:
                controller._handle_primary_action()
                return
            controller._toggle_expanded()

        def drawRect_(self, rect):
            self._draw_panel()

        @objc.python_method
        def _color(self, r, g, b, a=1.0):
            from AppKit import NSColor
            return NSColor.colorWithCalibratedRed_green_blue_alpha_(r / 255, g / 255, b / 255, a)

        @objc.python_method
        def _fill_round_rect(self, rect, radius, color):
            from AppKit import NSBezierPath
            color.setFill()
            NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(rect, radius, radius).fill()

        @objc.python_method
        def _draw_panel(self):
            from AppKit import (
                NSBezierPath, NSFont, NSForegroundColorAttributeName, NSMakeRect,
                NSFontAttributeName,
            )

            c = self._controller
            bounds = self.bounds()

            if c._expanded:
                self._fill_round_rect(NSMakeRect(2, 4, bounds.size.width - 4, bounds.size.height - 8), 24, self._color(9, 14, 25, 0.96))

            self._draw_ball()
            if not c._expanded:
                return

            title_attrs = {
                NSFontAttributeName: NSFont.boldSystemFontOfSize_(15),
                NSForegroundColorAttributeName: self._color(255, 255, 255, 0.92),
            }
            sub_attrs = {
                NSFontAttributeName: NSFont.monospacedDigitSystemFontOfSize_weight_(11, 0.45),
                NSForegroundColorAttributeName: self._color(206, 218, 240, 0.62),
            }
            ("正在听" if c._listening else "待命").drawInRect_withAttributes_(NSMakeRect(82, 20, 88, 22), title_attrs)
            (c._time_text if c._listening else "READY").drawInRect_withAttributes_(NSMakeRect(142, 22, 54, 18), sub_attrs)

            for i, level in enumerate(c._bars):
                h = 6 + level * 14
                color = self._color(75, 198, 121, 0.72) if c._listening else self._color(126, 148, 184, 0.58)
                self._fill_round_rect(NSMakeRect(82 + i * 8, 64 - h / 2, 4, h), 2, color)

            action = NSMakeRect(188, 27, 44, 44)
            self._fill_round_rect(action, 14, self._color(255, 76, 68, 0.9) if c._listening else self._color(75, 198, 121, 0.9))
            self._color(255, 255, 255, 0.92).setFill()
            if c._listening:
                self._fill_round_rect(NSMakeRect(204, 43, 12, 12), 3, self._color(255, 255, 255, 0.92))
            else:
                path = NSBezierPath.bezierPath()
                path.moveToPoint_((204, 40))
                path.lineToPoint_((204, 58))
                path.lineToPoint_((219, 49))
                path.closePath()
                path.fill()

        @objc.python_method
        def _draw_ball(self):
            from AppKit import NSBezierPath, NSMakeRect

            c = self._controller
            glow_color = self._color(80, 222, 138, 0.48 if c._listening else 0.2)
            glow_color.setFill()
            NSBezierPath.bezierPathWithOvalInRect_(NSMakeRect(0, 0, 64, 64)).fill()

            self._color(10, 16, 28, 0.98).setFill()
            NSBezierPath.bezierPathWithOvalInRect_(NSMakeRect(7, 7, 50, 50)).fill()

            bar_color = self._color(82, 216, 132, 0.82) if c._listening else self._color(126, 148, 184, 0.74)
            for i, level in enumerate(c._bars[:3]):
                h = 8 + level * 14
                self._fill_round_rect(NSMakeRect(23 + i * 7, 32 - h / 2, 4, h), 2, bar_color)

except Exception as e:
    print(f"NativeVoiceBall view init failed: {e}", flush=True)
    _NativeVoiceBallView = None


def should_use_native_voice_ball() -> bool:
    """Native AppKit view is currently opt-in because the default path crashes on launch."""
    return os.environ.get("MAC_TOOLS_USE_NATIVE_VOICE_BALL") == "1" and _NativeVoiceBallView is not None


# ═══════════════════════════════════════════════════════════
#  操作行
# ═══════════════════════════════════════════════════════════

class ActionRow(QFrame):
    clicked = pyqtSignal()

    def __init__(self, icon: str, title: str, hotkey_display: str, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(48)
        self._active = False
        self._hover = False

        self.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['bg']};
                border-radius: {SIZES['radius_md']};
                border: none;
            }}
        """)
        add_shadow(self, blur=14, opacity=0.035, y_offset=1)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 0, 14, 0)

        self._icon_frame = QFrame()
        self._icon_frame.setFixedSize(30, 30)
        self._icon_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['bg_input']};
                border-radius: 7px; border: none;
            }}
        """)
        il = QVBoxLayout(self._icon_frame)
        il.setContentsMargins(0, 0, 0, 0)
        self._icon_lbl = QLabel(icon)
        self._icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._icon_lbl.setStyleSheet("background: transparent; border: none; font-size: 14px;")
        il.addWidget(self._icon_lbl)
        layout.addWidget(self._icon_frame)
        layout.addSpacing(8)

        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(f"""
            font-size: 15px; font-weight: 500;
            color: {COLORS['text_primary']};
            background: transparent; border: none;
        """)
        layout.addWidget(title_lbl, 1)

        self._badge = QLabel(hotkey_display)
        self._badge.setStyleSheet(hotkey_badge_style())
        layout.addWidget(self._badge)

    def update_hotkey(self, display: str):
        self._badge.setText(display)

    def set_active_style(self, active: bool):
        self._active = active
        if active:
            self._icon_frame.setStyleSheet(f"""
                QFrame {{ background-color: {COLORS['danger']}; border-radius: 7px; border: none; }}
            """)
            self._icon_lbl.setStyleSheet("background: transparent; border: none; font-size: 14px; color: white;")
        else:
            self._icon_frame.setStyleSheet(f"""
                QFrame {{ background-color: {COLORS['bg_input']}; border-radius: 7px; border: none; }}
            """)
            self._icon_lbl.setStyleSheet("background: transparent; border: none; font-size: 14px;")

    def mousePressEvent(self, event):
        self.setStyleSheet(f"QFrame {{ background-color: {COLORS['bg_subtle']}; border-radius: {SIZES['radius_md']}; border: none; }}")
        QTimer.singleShot(0, self._emit_clicked_safe)

    def mouseReleaseEvent(self, event):
        self._update_hover_style()

    def _emit_clicked_safe(self):
        try:
            self.clicked.emit()
        except Exception:
            traceback.print_exc()

    def enterEvent(self, event):
        self._hover = True
        self._update_hover_style()

    def leaveEvent(self, event):
        self._hover = False
        self._update_hover_style()

    def _update_hover_style(self):
        if self._active:
            return
        if self._hover:
            self.setStyleSheet(f"QFrame {{ background-color: {COLORS['bg_hover']}; border-radius: {SIZES['radius_md']}; border: none; }}")
        else:
            self.setStyleSheet(f"QFrame {{ background-color: {COLORS['bg']}; border-radius: {SIZES['radius_md']}; border: none; }}")


# ═══════════════════════════════════════════════════════════
#  主窗口
# ═══════════════════════════════════════════════════════════

class MainWindow(QMainWindow):

    def __init__(self, local_test: bool = False):
        super().__init__()
        self.setWindowTitle("Mac Tools")
        self.setFixedSize(420, 160)
        self._local_test = local_test

        # 组件
        self.recorder = AudioRecorder()
        self.recognizer = SpeechRecognizer()
        self.hotkey_manager = HotkeyManager()
        self.clipboard_history = ClipboardHistoryService(
            ClipboardHistoryStore(
                CLIPBOARD_HISTORY_FILE,
                max_items=DEFAULT_CLIPBOARD_HISTORY_LIMIT,
                max_text_length=DEFAULT_CLIPBOARD_TEXT_MAX_LENGTH,
            ),
            self,
        )

        self.pin_windows: List[PinWindow] = []
        self.is_recording = False
        self.current_screenshot = None
        self._restore_after_screenshot = False
        self._voice_press_pending = False  # 长按录音延迟启动标记
        self._hotkey_permission_prompt_shown = False
        self._hotkey_permission_retry_count = 0
        self._hotkeys_ready_notified = False
        self._restore_after_recording = False
        self._voice_target_bundle_id = None

        # 线程安全桥 — 从 pynput 后台线程转发到 GUI 线程
        self._bridge = ThreadSafeBridge()
        self._bridge.screenshot_requested.connect(
            self._take_region_screenshot, Qt.ConnectionType.QueuedConnection)
        self._bridge.clipboard_history_requested.connect(
            self.show_clipboard_history, Qt.ConnectionType.QueuedConnection)
        self._bridge.voice_toggle_requested.connect(
            self.toggle_recording, Qt.ConnectionType.QueuedConnection)
        self._bridge.voice_press.connect(
            self._on_hotkey_voice_press, Qt.ConnectionType.QueuedConnection)
        self._bridge.voice_release.connect(
            self._on_hotkey_voice_release, Qt.ConnectionType.QueuedConnection)

        # 活跃线程引用（防止垃圾回收）
        self._active_threads = []

        # 配置
        self._config = load_user_config()
        self._hotkey_screenshot = self._config.get(
            "hotkey_screenshot", DEFAULT_HOTKEYS.get("screenshot", "<cmd>+<shift>+s"))
        self._hotkey_voice = self._config.get(
            "hotkey_voice_input", DEFAULT_HOTKEYS.get("voice_input", "<cmd>+<shift>+v"))
        self._hotkey_clipboard = self._config.get(
            "hotkey_clipboard_history", DEFAULT_HOTKEYS.get("clipboard_history", "<cmd>+<shift>+h"))
        self._notifications_enabled = self._config.get("show_notifications", True)
        self._clipboard_history_auto_paste = self._config.get("clipboard_history_auto_paste", False)

        self.init_ui()
        self.init_tray()
        self.clipboard_history.set_enabled(self._config.get("clipboard_history_enabled", False))
        self.init_hotkeys()

    @staticmethod
    def _format_hotkey(key_str: str) -> str:
        parts = key_str.replace("<", "").replace(">", "").split("+")
        symbols = {"cmd": "⌘", "shift": "⇧", "ctrl": "⌃", "alt": "⌥", "fn": "fn"}
        return " ".join(symbols.get(p.lower().strip(), p.upper()) for p in parts)

    # ── UI ────────────────────────────────────────────

    def init_ui(self):
        self.setStyleSheet(GLOBAL_STYLESHEET)

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(20, 14, 20, 10)
        root.setSpacing(0)

        # ── 顶栏 ─────────────────────────────────
        header = QFrame()
        header.setStyleSheet("QFrame { background: transparent; border: none; }")
        header.setFixedHeight(36)
        hl = QHBoxLayout(header)
        hl.setContentsMargins(2, 0, 0, 0)

        title = QLabel("Mac Tools")
        title.setStyleSheet(f"""
            font-size: 19px; font-weight: 700;
            color: {COLORS['text_primary']};
            letter-spacing: -0.5px;
        """)
        hl.addWidget(title)
        hl.addStretch()

        self._api_dot = QLabel()
        self._api_dot.setFixedSize(6, 6)
        has_api = bool(MIMO_API_KEY)
        self._api_dot.setStyleSheet(f"""
            background-color: {COLORS['success'] if has_api else COLORS['warning']};
            border-radius: 3px; border: none;
        """)
        self._api_dot.setToolTip("API 已连接" if has_api else "未配置 API Key")
        hl.addWidget(self._api_dot)
        hl.addSpacing(6)

        settings_btn = QPushButton("⚙︎")
        settings_btn.setFixedSize(28, 28)
        settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        settings_btn.setToolTip("设置")
        settings_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; border: none;
                border-radius: {SIZES['radius_sm']};
                font-size: 17px; color: {COLORS['text_hint']};
            }}
            QPushButton:hover {{ background: {COLORS['bg_hover']}; color: {COLORS['text_secondary']}; }}
        """)
        settings_btn.clicked.connect(self.show_settings)
        hl.addWidget(settings_btn)

        root.addWidget(header)
        root.addSpacing(10)

        # ── 操作行 ───────────────────────────────
        self._screenshot_row = ActionRow(
            "📷", "截图", self._format_hotkey(self._hotkey_screenshot))
        self._screenshot_row.clicked.connect(self._take_region_screenshot)
        root.addWidget(self._screenshot_row)
        root.addSpacing(6)

        self._voice_row = ActionRow(
            "🎙", "语音输入", self._format_hotkey(self._hotkey_voice))
        self._voice_row.clicked.connect(self.toggle_recording)
        root.addWidget(self._voice_row)

        root.addStretch()

        # ── 截图 Overlay ───────────────────────
        self._screenshot_overlay = ScreenshotOverlay()
        self._screenshot_overlay.completed.connect(self._on_screenshot_completed)
        self._screenshot_overlay.pin_requested.connect(self._on_screenshot_pin_requested)
        self._screenshot_overlay.cancelled.connect(self._on_screenshot_cancelled)

        # ── 浮动录音指示器 ──────────────────────
        if should_use_native_voice_ball():
            self._record_indicator = NativeVoiceBall()
        else:
            self._record_indicator = RecordingIndicator()
        self._record_indicator.stop_requested.connect(self.toggle_recording)

        # ── 录音计时器 ──────────────────────────
        self._record_timer = QTimer(self)  # 绑定 self 作为父对象
        self._record_timer.timeout.connect(self._update_record_time)
        self._record_seconds = 0

        self._level_timer = QTimer(self)
        self._level_timer.timeout.connect(self._update_record_level)

        QTimer.singleShot(0, self._record_indicator.show_idle)

    # ── 系统托盘 ──────────────────────────────────

    def init_tray(self):
        self._tray = QSystemTrayIcon(self)

        icon = QPixmap(32, 32)
        icon.fill(Qt.GlobalColor.transparent)
        p = QPainter(icon)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(COLORS["accent"]))
        p.drawRoundedRect(2, 2, 28, 28, 8, 8)
        p.setPen(QColor("white"))
        font = QFont("PingFang SC", 14, QFont.Weight.Bold)
        p.setFont(font)
        p.drawText(icon.rect(), Qt.AlignmentFlag.AlignCenter, "M")
        p.end()
        self._tray.setIcon(QIcon(icon))
        self._tray.setToolTip("Mac Tools")

        tray_menu = QMenu()
        tray_menu.setStyleSheet(f"""
            QMenu {{
                background-color: rgba(255,255,255,0.95);
                border: 1px solid rgba(0,0,0,0.08);
                border-radius: 8px; padding: 4px;
            }}
            QMenu::item {{ padding: 7px 20px; border-radius: 4px; font-size: 13px; }}
            QMenu::item:selected {{ background-color: {COLORS['accent']}; color: white; }}
        """)

        show_action = QAction("显示窗口", self)
        show_action.triggered.connect(self._show_window)
        tray_menu.addAction(show_action)

        screenshot_action = QAction("截图", self)
        screenshot_action.triggered.connect(self._take_region_screenshot)
        tray_menu.addAction(screenshot_action)

        settings_action = QAction("设置", self)
        settings_action.triggered.connect(self.show_settings)
        tray_menu.addAction(settings_action)

        clipboard_action = QAction("剪贴板历史", self)
        clipboard_action.triggered.connect(self.show_clipboard_history)
        tray_menu.addAction(clipboard_action)

        tray_menu.addSeparator()

        diagnostics_action = QAction("运行诊断", self)
        diagnostics_action.triggered.connect(self._show_diagnostics)
        tray_menu.addAction(diagnostics_action)

        permissions_menu = tray_menu.addMenu("权限设置")
        accessibility_action = QAction("辅助功能", self)
        accessibility_action.triggered.connect(self._open_accessibility_settings)
        permissions_menu.addAction(accessibility_action)

        input_action = QAction("输入监控", self)
        input_action.triggered.connect(self._open_input_monitoring_settings)
        permissions_menu.addAction(input_action)

        screen_action = QAction("屏幕录制", self)
        screen_action.triggered.connect(self._open_screen_recording_settings)
        permissions_menu.addAction(screen_action)

        microphone_action = QAction("麦克风", self)
        microphone_action.triggered.connect(self._open_microphone_settings)
        permissions_menu.addAction(microphone_action)

        tray_menu.addSeparator()

        quit_action = QAction("退出", self)
        quit_action.triggered.connect(self._quit_app)
        tray_menu.addAction(quit_action)

        self._tray_menu = tray_menu
        self._tray.activated.connect(self._on_tray_activated)
        self._tray.show()

    def _show_window(self):
        self.show()
        self.raise_()
        self.activateWindow()

    def _notify(self, title: str, message: str, icon=None, duration=3000):
        """Show user-visible feedback for background/menu-bar failures."""
        if not getattr(self, "_notifications_enabled", True):
            return
        try:
            tray_icon = icon or QSystemTrayIcon.MessageIcon.Information
            self._tray.showMessage(title, message, tray_icon, duration)
        except Exception:
            pass

    def _notify_error(self, title: str, message: str):
        self._notify(title, message, QSystemTrayIcon.MessageIcon.Critical, 5000)

    def _show_diagnostics(self):
        report = format_diagnostics_report(collect_diagnostics())
        QMessageBox.information(self, "运行诊断", report)

    def show_clipboard_history(self):
        menu = QMenu()
        menu.setStyleSheet(f"""
            QMenu {{
                background-color: rgba(255,255,255,0.96);
                border: 1px solid rgba(0,0,0,0.16);
                border-radius: 12px;
                padding: 0;
            }}
        """)
        content = ClipboardHistoryMenuContent(self.clipboard_history.store.texts(), menu)
        action = QWidgetAction(menu)
        action.setDefaultWidget(content)
        menu.addAction(action)
        target_bundle_id = self._frontmost_bundle_id()

        def close_menu():
            menu.close()

        def use_selected_text(text: str):
            close_menu()
            QTimer.singleShot(
                150,
                lambda selected=text, bundle_id=target_bundle_id:
                    self._use_clipboard_history_text(selected, target_bundle_id=bundle_id)
            )

        content.text_selected.connect(use_selected_text)
        content.clear_requested.connect(self.clipboard_history.clear)
        content.settings_requested.connect(close_menu)
        content.settings_requested.connect(self.show_settings)
        content.show_window_requested.connect(close_menu)
        content.show_window_requested.connect(self._show_window)
        content.quit_requested.connect(close_menu)
        content.quit_requested.connect(self._quit_app)

        self._clipboard_history_menu = menu
        menu.aboutToHide.connect(lambda: setattr(self, "_clipboard_history_menu", None))
        menu.popup(self._menu_position(content.sizeHint().width(), content.sizeHint().height()))
        QTimer.singleShot(0, content.search_input.setFocus)

    def _menu_position(self, menu_width: int, menu_height: int):
        tray_geometry = self._tray.geometry() if hasattr(self, "_tray") else None
        if tray_geometry and tray_geometry.isValid():
            anchor = tray_geometry.bottomRight()
        else:
            anchor = QCursor.pos()
        screen = QApplication.screenAt(anchor) or QApplication.primaryScreen()
        if not screen:
            return anchor
        available = screen.availableGeometry()
        x = min(max(anchor.x() - menu_width + 16, available.left()), available.right() - menu_width)
        y = min(max(anchor.y() + 6, available.top()), available.bottom() - menu_height)
        return QPoint(x, y)

    def _frontmost_bundle_id(self):
        try:
            app = NSWorkspace.sharedWorkspace().frontmostApplication()
            bundle_id = app.bundleIdentifier() if app else None
            if bundle_id and bundle_id != "com.mactools.screenshot-voice":
                return str(bundle_id)
        except Exception:
            pass
        return None

    def _use_clipboard_history_text(self, text: str, target_bundle_id: str | None = None):
        if not text:
            return
        if self._clipboard_history_auto_paste:
            result = type_text(text, target_bundle_id=target_bundle_id)
            if result == "pasted":
                self._notify("已粘贴剪贴板历史", text[:60])
            elif result == "copied":
                self._notify("已复制剪贴板历史", "目标应用未允许自动粘贴，请按 Cmd+V")
            else:
                self._notify_error("剪贴板历史失败", "未能复制或粘贴所选内容")
            return
        if self.clipboard_history.copy_text(text):
            self._notify("已复制剪贴板历史", text[:60])

    def _open_privacy_settings(self, permission: str, label: str):
        if open_privacy_settings(permission):
            self._notify("已打开系统设置", f"请允许「{label}」权限", duration=5000)
        else:
            self._notify_error("无法打开系统设置", "请手动打开 系统设置 > 隐私与安全")

    def _open_accessibility_settings(self):
        self._open_privacy_settings("accessibility", "辅助功能")

    def _open_input_monitoring_settings(self):
        self._open_privacy_settings("input_monitoring", "输入监控")

    def _show_hotkey_permissions_setup(self):
        if self._hotkey_permission_prompt_shown:
            return
        self._hotkey_permission_prompt_shown = True

        if not is_accessibility_trusted():
            prompt_accessibility_permission()
        if not is_input_monitoring_trusted():
            prompt_input_monitoring_permission()
        self._show_window()

        box = QMessageBox(self)
        box.setWindowTitle("需要快捷键权限")
        box.setIcon(QMessageBox.Icon.Warning)
        box.setText("全局快捷键需要开启辅助功能和输入监控权限。")
        box.setInformativeText(
            "本地测试时，请在 系统设置 > 隐私与安全 中为「Mac截图语音工具」启用"
            "「辅助功能」和「输入监控」。如果列表里有多个同名项，先删除 "
            "/Applications 里的旧版本，只保留当前 dist 中启动的本地测试版本。"
        )
        accessibility_button = box.addButton("打开辅助功能设置", QMessageBox.ButtonRole.AcceptRole)
        input_button = box.addButton("打开输入监控设置", QMessageBox.ButtonRole.ActionRole)
        box.addButton("稍后", QMessageBox.ButtonRole.RejectRole)
        box.exec()
        if box.clickedButton() == accessibility_button:
            self._open_accessibility_settings()
        elif box.clickedButton() == input_button:
            self._open_input_monitoring_settings()

    def _open_screen_recording_settings(self):
        self._open_privacy_settings("screen_recording", "屏幕录制")

    def _open_microphone_settings(self):
        self._open_privacy_settings("microphone", "麦克风")

    def _show_screen_recording_setup(self):
        prompt_screen_recording_permission()
        self._show_window()

        box = QMessageBox(self)
        box.setWindowTitle("需要屏幕录制权限")
        box.setIcon(QMessageBox.Icon.Warning)
        box.setText("截图功能需要开启屏幕录制权限。")
        box.setInformativeText(
            "请在 系统设置 > 隐私与安全 > 屏幕录制 中启用「Mac截图语音工具」。"
            "修改后请退出并重新打开应用，让 macOS 权限生效。"
        )
        open_button = box.addButton("打开屏幕录制设置", QMessageBox.ButtonRole.AcceptRole)
        box.addButton("稍后", QMessageBox.ButtonRole.RejectRole)
        box.exec()
        if box.clickedButton() == open_button:
            self._open_screen_recording_settings()

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.show_clipboard_history()
        elif reason == QSystemTrayIcon.ActivationReason.Context:
            self._tray_menu.popup(self._menu_position(220, 360))

    def _quit_app(self):
        self._tray.hide()
        self.hotkey_manager.stop()
        self._record_timer.stop()
        self._level_timer.stop()
        self._record_indicator.close()
        try:
            self.recorder.close()
        except Exception:
            pass
        # 等待所有线程结束
        for t in self._active_threads:
            if t.isRunning():
                t.quit()
                t.wait(2000)
        for pin in list(self.pin_windows):
            try:
                pin.close()
            except Exception:
                pass
        QApplication.quit()

    # ── 窗口行为 ──────────────────────────────────

    def closeEvent(self, event):
        event.ignore()
        self.hide()

    # ── 截图 ────────────────────────────────────────

    def _take_region_screenshot(self):
        if is_screen_recording_trusted() is False:
            self._notify_error("截图失败", "请先允许屏幕录制权限")
            self._show_screen_recording_setup()
            return
        was_visible = self.isVisible()
        self._restore_after_screenshot = was_visible
        if was_visible:
            self.hide()
        QTimer.singleShot(200, self._start_screenshot_overlay)

    def _start_screenshot_overlay(self):
        try:
            if is_screen_recording_trusted() is False:
                self._notify_error("截图失败", "请先允许屏幕录制权限")
                self._show_screen_recording_setup()
                self._restore_main_after_screenshot()
                return
            if not self._screenshot_overlay.start():
                self._notify_error("截图失败", "无法启动截图窗口")
                self._restore_main_after_screenshot()
        except Exception as e:
            print(f"截图失败: {e}")
            if is_screen_recording_trusted() is False:
                self._notify_error("截图失败", "请检查屏幕录制权限后重试")
                self._show_screen_recording_setup()
            else:
                message = str(e).strip() or "系统截图命令执行失败"
                self._notify_error("截图失败", message)
            self._restore_main_after_screenshot()

    def _restore_main_after_screenshot(self):
        if self._restore_after_screenshot and not self.isVisible():
            self._show_window()
        self._restore_after_screenshot = False

    def _on_screenshot_completed(self, path: str):
        if path:
            self._notify("截图已保存", path, QSystemTrayIcon.MessageIcon.Information, 3000)
        else:
            self._notify("截图已复制", "已复制到剪贴板", QSystemTrayIcon.MessageIcon.Information, 2000)
        self._restore_main_after_screenshot()

    def _on_screenshot_pin_requested(self, pixmap: QPixmap):
        self._create_pin_window(pixmap)
        self._notify("截图已贴到桌面", "可拖动、缩放或右键操作", QSystemTrayIcon.MessageIcon.Information, 2000)
        self._restore_main_after_screenshot()

    def _on_screenshot_cancelled(self):
        self._notify("截图已取消", "未保存截图", QSystemTrayIcon.MessageIcon.Information, 2000)
        self._restore_main_after_screenshot()

    # ── 贴图 ────────────────────────────────────────

    def _create_pin_window(self, pixmap: QPixmap):
        pin = PinWindow(pixmap)
        pin.closed.connect(lambda p=pin: self._safe_pin_closed(p))
        pin.show()
        self.pin_windows.append(pin)

    def _safe_pin_closed(self, pin):
        """安全移除 pin 窗口"""
        try:
            if pin in self.pin_windows:
                self.pin_windows.remove(pin)
        except Exception:
            pass

    # ── 语音 — 流式识别 + 浮动指示器 ──────────────

    def toggle_recording(self):
        if self.is_recording:
            self._stop_recording()
        else:
            self._start_recording()

    def _start_recording(self):
        self._restore_after_recording = self.isVisible()
        self._voice_target_bundle_id = getattr(self, "_frontmost_bundle_id", lambda: None)()
        self.is_recording = True
        self._voice_row.set_active_style(True)
        try:
            self.recorder.start_recording()
        except Exception as e:
            print(f"录音启动失败: {e}")
            self._notify_error("录音启动失败", "请检查麦克风权限或输入设备")
            self.is_recording = False
            self._voice_row.set_active_style(False)
            return

        self._record_seconds = 0
        self._record_timer.start(1000)
        self._level_timer.start(80)

        self._record_indicator.start()
        self._record_indicator.set_time("00:00")
        self._record_indicator.set_audio_level(0.0)

        # Keep the main window available while recording. Hiding here makes the
        # app look broken when users start recording from the main window.

    def _stop_recording(self):
        self.is_recording = False
        self._voice_row.set_active_style(False)
        self._record_timer.stop()
        self._level_timer.stop()

        try:
            audio_path = self.recorder.stop_recording()
        except Exception as e:
            print(f"停止录音失败: {e}")
            if hasattr(self._record_indicator, "show_error"):
                self._record_indicator.show_error("录音文件未能正常保存")
            else:
                self._record_indicator.stop()
            self._notify_error("录音停止失败", "录音文件未能正常保存")
            return

        if audio_path:
            if hasattr(self._record_indicator, "show_transcribing"):
                self._record_indicator.show_transcribing()
            else:
                self._record_indicator.stop()
            self._stream_recognize(audio_path)
        else:
            if hasattr(self._record_indicator, "show_error"):
                self._record_indicator.show_error("没有检测到录音内容")
            else:
                self._record_indicator.stop()
            self._notify("录音已取消", "没有检测到可保存的录音内容", QSystemTrayIcon.MessageIcon.Warning, 3000)
            if self._restore_after_recording and not self.isVisible():
                self._show_window()
            self._restore_after_recording = False

    def _update_record_time(self):
        self._record_seconds += 1
        m, s = divmod(self._record_seconds, 60)
        self._record_indicator.set_time(f"{m:02d}:{s:02d}")

    def _update_record_level(self):
        try:
            self._record_indicator.set_audio_level(self.recorder.get_audio_level())
        except Exception:
            self._record_indicator.set_audio_level(0.0)

    def _stream_recognize(self, audio_path: str):
        if not self.recognizer.is_available():
            print("[ASR] 不可用")
            if hasattr(self._record_indicator, "show_error"):
                self._record_indicator.show_error("语音识别不可用")
            self._notify_error("语音识别不可用", "请检查 API Key 或网络连接")
            if self._restore_after_recording and not self.isVisible():
                self._show_window()
            self._restore_after_recording = False
            return

        # 清理旧线程
        self._cleanup_threads()
        if self._has_running_recognition():
            if hasattr(self._record_indicator, "show_error"):
                self._record_indicator.show_error("上一次识别仍在进行")
            self._notify("语音识别进行中", "请等待上一次识别完成", QSystemTrayIcon.MessageIcon.Warning, 3000)
            if self._restore_after_recording and not self.isVisible():
                self._show_window()
            self._restore_after_recording = False
            return

        if hasattr(self._record_indicator, "show_transcribing"):
            self._record_indicator.show_transcribing()

        thread = SimpleRecognitionThread(self.recognizer, audio_path)
        thread.finished.connect(self._on_recognition_finished)
        thread.error.connect(self._on_recognition_error)
        thread.finished.connect(lambda: self._remove_thread(thread))
        thread.error.connect(lambda _: self._remove_thread(thread))

        self._active_threads.append(thread)
        thread.start()

    def _on_recognition_finished(self, full_text: str):
        try:
            if full_text and full_text.strip():
                if self.isVisible() and not self._restore_after_recording:
                    self.hide()
                # 短延迟确保焦点回到目标应用
                QTimer.singleShot(100, lambda: self._paste_and_notify(full_text.strip()))
            else:
                if hasattr(self._record_indicator, "show_error"):
                    self._record_indicator.show_error("没有识别到文字")
                self._notify("语音识别为空", "没有识别到可输入的文字", QSystemTrayIcon.MessageIcon.Warning, 3000)
        except Exception as e:
            print(f"[ASR] 输入失败: {e}")
            if hasattr(self._record_indicator, "show_error"):
                self._record_indicator.show_error("识别结果处理失败")

    def _paste_and_notify(self, text: str):
        """粘贴文字到目标应用，然后通知用户"""
        try:
            result = type_text(text, target_bundle_id=self._voice_target_bundle_id)
            self._voice_target_bundle_id = None
            print(f"[ASR] 输入结果: {result}, {text[:50]}")
        except Exception as e:
            print(f"[ASR] 粘贴失败: {e}")
            if hasattr(self._record_indicator, "show_error"):
                self._record_indicator.show_error("识别结果未能输入")
            self._notify_error("文字输入失败", "识别结果未能写入剪贴板")
            return

        if result == "pasted":
            if hasattr(self._record_indicator, "show_done"):
                self._record_indicator.show_done(f"已插入 {len(text)} 字")
            self._notify(
                "语音识别完成",
                text[:60],
                QSystemTrayIcon.MessageIcon.Information,
                3000
            )
        elif result == "copied":
            if hasattr(self._record_indicator, "show_done"):
                self._record_indicator.show_done(f"已复制 {len(text)} 字")
            self._notify(
                "已复制识别结果",
                "目标应用未允许自动粘贴，请按 Cmd+V",
                QSystemTrayIcon.MessageIcon.Warning,
                5000
            )
        else:
            if hasattr(self._record_indicator, "show_error"):
                self._record_indicator.show_error("识别结果未能输入")
            self._notify_error("文字输入失败", "识别结果未能写入剪贴板")

        # 延迟后再恢复主窗口，不抢占焦点
        QTimer.singleShot(500, self._restore_window_after_paste)

    def _restore_window_after_paste(self):
        """粘贴完成后恢复主窗口"""
        # 不再自动显示窗口，用户可以通过托盘图标或快捷键打开
        pass

    def _on_recognition_error(self, error: str):
        print(f"[ASR] 错误: {error}")
        if hasattr(self._record_indicator, "show_error"):
            self._record_indicator.show_error(str(error)[:60] or "语音识别失败")
        self._notify_error("语音识别失败", str(error)[:120])

    def _cleanup_threads(self):
        """清理已完成的线程"""
        for t in list(self._active_threads):
            if not t.isRunning():
                self._active_threads.remove(t)

    def _has_running_recognition(self) -> bool:
        return any(t.isRunning() for t in self._active_threads)

    def _remove_thread(self, thread):
        """从活跃线程列表移除"""
        if thread in self._active_threads:
            self._active_threads.remove(thread)

    # ── 设置 ────────────────────────────────────────

    def show_settings(self):
        restart_hotkeys = bool(getattr(self.hotkey_manager, "is_running", False))
        if restart_hotkeys:
            self.hotkey_manager.stop()

        try:
            dialog = SettingsDialog(self)
            accepted = dialog.exec() == QDialog.DialogCode.Accepted
            if accepted:
                self._config = load_user_config()
                self._notifications_enabled = self._config.get("show_notifications", True)
                self.clipboard_history.set_enabled(self._config.get("clipboard_history_enabled", False))
                self._clipboard_history_auto_paste = self._config.get("clipboard_history_auto_paste", False)
                new_key = self._config.get("mimo_api_key", "")
                self._api_dot.setStyleSheet(f"""
                    background-color: {COLORS['success'] if new_key else COLORS['warning']};
                    border-radius: 3px; border: none;
                """)
                if new_key:
                    self.recognizer = SpeechRecognizer(api_key=new_key)

                ns = self._config.get("hotkey_screenshot", DEFAULT_HOTKEYS["screenshot"])
                nv = self._config.get("hotkey_voice_input", DEFAULT_HOTKEYS["voice_input"])
                nc = self._config.get("hotkey_clipboard_history", DEFAULT_HOTKEYS["clipboard_history"])
                if ns != self._hotkey_screenshot or nv != self._hotkey_voice or nc != self._hotkey_clipboard:
                    self._hotkey_screenshot = ns
                    self._hotkey_voice = nv
                    self._hotkey_clipboard = nc
                    self._screenshot_row.update_hotkey(self._format_hotkey(ns))
                    self._voice_row.update_hotkey(self._format_hotkey(nv))
                    self.hotkey_manager.update_hotkey("screenshot", ns)
                    self.hotkey_manager.update_hotkey("voice_input", nv)
                    self.hotkey_manager.update_hotkey("clipboard_history", nc)
        finally:
            if restart_hotkeys and self._hotkey_permissions_ready():
                self.hotkey_manager.start()

    def init_hotkeys(self):
        # 截图 — 普通按下触发
        self.hotkey_manager.register_hotkey(
            "screenshot", self._hotkey_screenshot,
            self._bridge.screenshot_requested.emit, "截图")
        # 语音 — 长按录音，松开转文字
        self.hotkey_manager.register_hold_hotkey(
            "voice_input", self._hotkey_voice,
            on_press=self._bridge.voice_press.emit,
            on_release=self._bridge.voice_release.emit,
            description="语音输入（长按）")
        self.hotkey_manager.register_hotkey(
            "clipboard_history", self._hotkey_clipboard,
            self._bridge.clipboard_history_requested.emit, "剪贴板历史")

        if not self._hotkey_permissions_ready():
            self._tray.setToolTip("Mac Tools - 需要辅助功能和输入监控权限启用全局快捷键")
            self._start_hotkey_permission_retry()
            QTimer.singleShot(500, self._show_hotkey_permissions_setup)
            return

        self.hotkey_manager.start()

    def _hotkey_permissions_ready(self):
        return is_accessibility_trusted() and is_input_monitoring_trusted()

    def _start_hotkey_permission_retry(self):
        self._hotkey_permission_retry_count = 0
        QTimer.singleShot(1000, self._poll_hotkey_permissions_for_hotkeys)

    def _poll_hotkey_permissions_for_hotkeys(self):
        if self._hotkey_permissions_ready():
            self.hotkey_manager.stop()
            self.hotkey_manager.start()
            self._tray.setToolTip("Mac Tools")
            if not self._hotkeys_ready_notified:
                self._notify("快捷键已启用", "辅助功能和输入监控权限已生效", duration=2500)
                self._hotkeys_ready_notified = True
            return

        self._hotkey_permission_retry_count += 1
        if self._hotkey_permission_retry_count < 60:
            QTimer.singleShot(2000, self._poll_hotkey_permissions_for_hotkeys)

    def _on_hotkey_voice_press(self):
        """长按快捷键按下 — 延迟启动录音，避免原生按键冲突"""
        if not self.is_recording:
            self._voice_press_pending = True
            # 延迟 150ms 让 macOS 完成按键事件处理
            QTimer.singleShot(150, self._deferred_start_recording)

    def _deferred_start_recording(self):
        """延迟后的实际录音启动"""
        if not self.is_recording and self._voice_press_pending:
            self._voice_press_pending = False
            self._start_recording()

    def _on_hotkey_voice_release(self):
        """长按快捷键释放 — 停止录音并识别"""
        self._voice_press_pending = False  # 取消延迟启动
        if self.is_recording:
            self._stop_recording()
