#!/usr/bin/env python3
"""
生成应用图标
"""

import os
from PIL import Image, ImageDraw, ImageFont

def create_icon():
    """创建应用图标"""
    
    # 图标尺寸
    sizes = [16, 32, 64, 128, 256, 512, 1024]
    
    # 创建图标目录
    iconset_dir = "icon.iconset"
    os.makedirs(iconset_dir, exist_ok=True)
    
    # 颜色定义
    bg_color = (52, 152, 219)  # 蓝色背景
    accent_color = (231, 76, 60)  # 红色强调
    white = (255, 255, 255)
    
    for size in sizes:
        # 创建图像
        img = Image.new('RGB', (size, size), bg_color)
        draw = ImageDraw.Draw(img)
        
        # 计算元素大小
        margin = size // 8
        icon_size = size - margin * 2
        
        # 绘制截图图标（相机形状）
        # 外框
        rect_margin = size // 6
        draw.rounded_rectangle(
            [rect_margin, rect_margin, size - rect_margin, size - rect_margin],
            radius=size // 10,
            fill=white,
            outline=bg_color,
            width=max(1, size // 50)
        )
        
        # 镜头圆圈
        center_x, center_y = size // 2, size // 2 - size // 20
        radius = size // 5
        draw.ellipse(
            [center_x - radius, center_y - radius, center_x + radius, center_y + radius],
            fill=bg_color,
            outline=white,
            width=max(1, size // 40)
        )
        
        # 内圆
        inner_radius = radius // 2
        draw.ellipse(
            [center_x - inner_radius, center_y - inner_radius, 
             center_x + inner_radius, center_y + inner_radius],
            fill=white
        )
        
        # 闪光灯
        flash_x = size // 2 + size // 5
        flash_y = rect_margin + size // 10
        flash_size = size // 12
        draw.rectangle(
            [flash_x - flash_size, flash_y - flash_size,
             flash_x + flash_size, flash_y + flash_size],
            fill=accent_color
        )
        
        # 麦克风图标（右下角）
        mic_x = size - size // 4
        mic_y = size - size // 4
        mic_width = size // 8
        mic_height = size // 5
        
        # 麦克风主体
        draw.rounded_rectangle(
            [mic_x - mic_width, mic_y - mic_height,
             mic_x + mic_width, mic_y + mic_height // 2],
            radius=mic_width,
            fill=accent_color
        )
        
        # 麦克风支架
        draw.arc(
            [mic_x - mic_width * 2, mic_y - mic_height // 2,
             mic_x + mic_width * 2, mic_y + mic_height * 2],
            start=0, end=180,
            fill=white,
            width=max(1, size // 50)
        )
        
        # 麦克风底座
        draw.line(
            [mic_x, mic_y + mic_height * 2 - mic_height // 2,
             mic_x, mic_y + mic_height * 2],
            fill=white,
            width=max(1, size // 50)
        )
        draw.line(
            [mic_x - mic_width, mic_y + mic_height * 2,
             mic_x + mic_width, mic_y + mic_height * 2],
            fill=white,
            width=max(1, size // 50)
        )
        
        # 保存不同尺寸
        if size <= 512:
            filename = f"icon_{size}x{size}.png"
        else:
            filename = f"icon_512x512@2x.png"
        
        img.save(os.path.join(iconset_dir, filename))
        
        # 保存@2x版本
        if size <= 256:
            img_2x = img.resize((size * 2, size * 2), Image.Resampling.LANCZOS)
            filename_2x = f"icon_{size}x{size}@2x.png"
            img_2x.save(os.path.join(iconset_dir, filename_2x))
    
    print("图标文件已生成到 icon.iconset 目录")
    
    # 使用iconutil创建icns文件（仅macOS）
    if os.system("which iconutil > /dev/null 2>&1") == 0:
        os.system("iconutil -c icns icon.iconset -o icon.icns")
        print("已创建 icon.icns 文件")
    else:
        print("警告: iconutil 命令不可用，无法创建 .icns 文件")
        print("请手动使用其他工具转换图标")

if __name__ == "__main__":
    create_icon()
