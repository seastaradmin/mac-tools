#!/usr/bin/env python3
"""
Mac截图语音工具 - 主程序入口
macOS 附件模式（LSUIElement）：不抢焦点、不出现在 Dock
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# ── 关键：在创建 QApplication 前设置 LSUIElement ──
# 这让应用成为"附件应用"，不抢焦点、不出现在 Dock/Cmd+Tab
from AppKit import (
    NSApplication,
    NSApplicationActivationPolicyAccessory,
)

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon

from app_metadata import APP_NAME, APP_VERSION
from ui.main_window import MainWindow
from ui.styles import GLOBAL_STYLESHEET


def main():
    """主函数"""
    os.chdir(project_root)
    local_test = "--local-test" in sys.argv

    ns_app = NSApplication.sharedApplication()
    # 设置 macOS 附件模式 — 这是防止抢焦点和不占 Dock 的核心。
    # 本地测试也必须保持菜单栏工具形态，避免和正式运行行为不一致。
    ns_app.setActivationPolicy_(NSApplicationActivationPolicyAccessory)

    # 创建 Qt 应用
    app = QApplication(sys.argv)

    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName("MacTools")

    # 关闭窗口不退出（托盘常驻）
    app.setQuitOnLastWindowClosed(False)

    # 全局样式
    app.setStyleSheet(GLOBAL_STYLESHEET)

    # 创建主窗口（初始隐藏，通过托盘打开）
    window = MainWindow(local_test=local_test)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
