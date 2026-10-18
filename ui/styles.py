"""
Apple 风格设计系统 v3 — 纯白 · 通透 · 轻盈
"""

# ============================================================
# 颜色系统 — 纯白底 + Apple Blue
# ============================================================
COLORS = {
    # 强调色
    "accent": "#007AFF",
    "accent_hover": "#0063D1",
    "accent_soft": "rgba(0,122,255,0.1)",

    # 功能色
    "success": "#34C759",
    "danger": "#FF3B30",
    "warning": "#FF9500",

    # 纯白底
    "bg": "#FFFFFF",
    "bg_card": "#FFFFFF",
    "bg_hover": "#F5F5F7",
    "bg_input": "#F5F5F7",
    "bg_subtle": "#E8E8ED",
    "bg_tertiary": "#F5F5F7",

    "text_primary": "#1D1D1F",
    "text_secondary": "#86868B",
    "text_hint": "#AEAEB2",
    "text_on_accent": "#FFFFFF",

    "border": "rgba(0,0,0,0.06)",
    "border_light": "rgba(0,0,0,0.03)",
    "border_focus": "#007AFF",
    "divider": "rgba(0,0,0,0.04)",

    # 兼容旧组件
    "bg_main": "#FFFFFF",
    "primary": "#007AFF",
    "primary_light": "rgba(0,122,255,0.08)",
    "primary_hover": "#0063D1",
    "text_on_primary": "#FFFFFF",
    "secondary": "#5856D6",
    "secondary_light": "rgba(88,86,214,0.08)",
    "danger_hover": "#D63029",
    "bg_sidebar": "#F5F5F7",
}

# ============================================================
# 尺寸
# ============================================================
SIZES = {
    "radius_sm": "8px",
    "radius_md": "12px",
    "radius_lg": "16px",
    "radius_xl": "20px",
    "radius_full": "9999px",
}

# ============================================================
# 全局样式
# ============================================================
GLOBAL_STYLESHEET = f"""
QMainWindow {{
    background-color: {COLORS['bg']};
}}
QWidget {{
    font-family: "PingFang SC", "Helvetica Neue", "Lucida Grande";
    color: {COLORS['text_primary']};
}}

/* 滚动条 */
QScrollBar:vertical {{
    background: transparent; width: 6px; margin: 0;
}}
QScrollBar::handle:vertical {{
    background: rgba(0,0,0,0.12); border-radius: 3px; min-height: 20px;
}}
QScrollBar::handle:vertical:hover {{ background: rgba(0,0,0,0.2); }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}

/* 文本框 */
QTextEdit {{
    background-color: {COLORS['bg_input']};
    border: none;
    border-radius: {SIZES['radius_md']};
    padding: 12px 14px;
    font-size: 14px;
    color: {COLORS['text_primary']};
    selection-background-color: rgba(0,122,255,0.15);
}}
QTextEdit:focus {{
    background-color: {COLORS['bg']};
}}

/* 输入框 */
QLineEdit {{
    background-color: {COLORS['bg_input']};
    border: none;
    border-radius: {SIZES['radius_md']};
    padding: 9px 14px;
    font-size: 14px;
    color: {COLORS['text_primary']};
}}

/* 状态栏 */
QStatusBar {{
    background-color: transparent;
    color: {COLORS['text_hint']};
    font-size: 12px;
    border: none;
}}

/* 对话框 */
QDialog {{ background-color: {COLORS['bg']}; }}

/* 工具提示 — 毛玻璃感 */
QToolTip {{
    background-color: rgba(29,29,31,0.75);
    color: white; border: none;
    border-radius: 5px; padding: 4px 8px;
    font-size: 11px; font-weight: 500;
}}

QMessageBox {{ background-color: {COLORS['bg_card']}; }}
"""

# ============================================================
# 组件样式
# ============================================================

def card_style(padding=20):
    return f"""
        background-color: {COLORS['bg_card']};
        border-radius: {SIZES['radius_lg']};
        border: none;
        padding: {padding}px;
    """

def primary_button_style(size="md"):
    sizes = {"sm": ("6px 14px", "13px"), "md": ("9px 18px", "14px"), "lg": ("12px 24px", "15px")}
    pad, fs = sizes.get(size, sizes["md"])
    return f"""
        QPushButton {{
            background-color: {COLORS['accent']};
            color: {COLORS['text_on_accent']};
            border: none; border-radius: {SIZES['radius_md']};
            padding: {pad}; font-size: {fs}; font-weight: 600;
        }}
        QPushButton:hover {{ background-color: {COLORS['accent_hover']}; }}
        QPushButton:pressed {{ background-color: #004EA2; }}
        QPushButton:disabled {{ background-color: {COLORS['bg_hover']}; color: {COLORS['text_hint']}; }}
    """

def ghost_button_style(size="md"):
    sizes = {"sm": ("5px 10px", "13px"), "md": ("7px 14px", "14px"), "lg": ("10px 20px", "15px")}
    pad, fs = sizes.get(size, sizes["md"])
    return f"""
        QPushButton {{
            background-color: transparent; color: {COLORS['accent']};
            border: none; border-radius: {SIZES['radius_sm']};
            padding: {pad}; font-size: {fs}; font-weight: 500;
        }}
        QPushButton:hover {{ background-color: {COLORS['accent_soft']}; }}
    """

def secondary_button_style(size="md"):
    sizes = {"sm": ("6px 14px", "13px"), "md": ("9px 18px", "14px"), "lg": ("12px 24px", "15px")}
    pad, fs = sizes.get(size, sizes["md"])
    return f"""
        QPushButton {{
            background-color: {COLORS['accent_soft']}; color: {COLORS['accent']};
            border: none; border-radius: {SIZES['radius_md']};
            padding: {pad}; font-size: {fs}; font-weight: 600;
        }}
        QPushButton:hover {{ background-color: rgba(0,122,255,0.15); }}
    """

def danger_button_style(size="md"):
    sizes = {"sm": ("6px 14px", "13px"), "md": ("9px 18px", "14px"), "lg": ("12px 24px", "15px")}
    pad, fs = sizes.get(size, sizes["md"])
    return f"""
        QPushButton {{
            background-color: {COLORS['danger']}; color: white;
            border: none; border-radius: {SIZES['radius_md']};
            padding: {pad}; font-size: {fs}; font-weight: 600;
        }}
        QPushButton:hover {{ background-color: #D63029; }}
    """

def icon_button_style(active=False):
    bg = COLORS["accent_soft"] if active else "transparent"
    color = COLORS["accent"] if active else COLORS["text_secondary"]
    return f"""
        QPushButton {{
            background-color: {bg}; color: {color};
            border: none; border-radius: {SIZES['radius_sm']};
            padding: 6px; font-size: 15px; min-width: 32px; min-height: 32px;
        }}
        QPushButton:hover {{ background-color: {COLORS['bg_hover']}; }}
    """

def sidebar_item_style(active=False):
    if active:
        return f"""
            QPushButton {{
                background-color: {COLORS['accent_soft']}; color: {COLORS['accent']};
                border: none; border-radius: {SIZES['radius_md']};
                padding: 10px 16px; font-size: 14px; font-weight: 600; text-align: left;
            }}
        """
    return f"""
        QPushButton {{
            background-color: transparent; color: {COLORS['text_primary']};
            border: none; border-radius: {SIZES['radius_md']};
            padding: 10px 16px; font-size: 14px; font-weight: 500; text-align: left;
        }}
        QPushButton:hover {{ background-color: {COLORS['bg_hover']}; }}
    """

def tab_style():
    return f"""
        QTabWidget::pane {{ border: none; background-color: {COLORS['bg']}; }}
        QTabBar::tab {{
            background-color: transparent; color: {COLORS['text_secondary']};
            padding: 10px 20px; border: none; border-bottom: 2px solid transparent;
            font-size: 14px; font-weight: 500;
        }}
        QTabBar::tab:selected {{ color: {COLORS['accent']}; border-bottom: 2px solid {COLORS['accent']}; font-weight: 600; }}
    """

def chip_style(color=None):
    c = color or COLORS["accent"]
    return f"""
        QLabel {{
            background-color: {c}15; color: {c};
            border-radius: {SIZES['radius_full']};
            padding: 3px 10px; font-size: 12px; font-weight: 600;
        }}
    """

def toolbar_floating_style():
    return f"""
        QFrame {{
            background-color: rgba(255,255,255,0.9);
            border-radius: {SIZES['radius_lg']};
            border: none; padding: 4px;
        }}
    """

def hotkey_badge_style():
    return f"""
        QLabel {{
            background-color: {COLORS['bg_input']};
            color: {COLORS['text_secondary']};
            border: none; border-radius: 6px;
            padding: 4px 10px;
            font-size: 12px; font-weight: 600;
            font-family: "Menlo", "Consolas", monospace;
        }}
    """
