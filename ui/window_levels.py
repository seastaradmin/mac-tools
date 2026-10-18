"""
macOS window level helpers for app-owned floating windows.
"""

from PyQt6.QtCore import QTimer


def keep_window_on_top(widget, *, non_activating=False):
    """Keep a Qt window above normal macOS windows and across Spaces."""
    if non_activating:
        try:
            from PyQt6.QtCore import Qt
            widget.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        except Exception:
            pass

    QTimer.singleShot(0, lambda: _apply_macos_level(widget))


def _apply_macos_level(widget):
    try:
        import objc
        from ctypes import c_void_p
        from AppKit import (
            NSFloatingWindowLevel,
            NSWindowCollectionBehaviorCanJoinAllSpaces,
            NSWindowCollectionBehaviorFullScreenAuxiliary,
            NSWindowCollectionBehaviorStationary,
        )

        view = objc.objc_object(c_void_p=c_void_p(int(widget.winId())))
        window = view.window()
        if not window:
            return

        behavior = (
            NSWindowCollectionBehaviorCanJoinAllSpaces
            | NSWindowCollectionBehaviorFullScreenAuxiliary
            | NSWindowCollectionBehaviorStationary
        )
        window.setLevel_(NSFloatingWindowLevel)
        window.setCollectionBehavior_(behavior)
        if hasattr(window, "setCanHide_"):
            window.setCanHide_(False)
        if hasattr(window, "setHidesOnDeactivate_"):
            window.setHidesOnDeactivate_(False)
        window.orderFrontRegardless()
    except Exception as e:
        print(f"设置窗口置顶失败: {e}")
