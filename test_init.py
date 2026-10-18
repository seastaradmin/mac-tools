#!/usr/bin/env python3
"""
测试程序初始化
"""

import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_init():
    """测试程序初始化"""
    print("测试程序初始化...")
    
    try:
        from PyQt6.QtWidgets import QApplication
        print("✓ PyQt6 导入成功")
        
        # 创建应用实例
        app = QApplication(sys.argv)
        print("✓ QApplication 创建成功")
        
        from ui.main_window import MainWindow
        print("✓ MainWindow 导入成功")
        
        # 测试窗口创建（不显示）
        window = MainWindow()
        print("✓ MainWindow 创建成功")
        
        # 测试配置
        from config import MIMO_API_KEY
        if MIMO_API_KEY:
            print("✓ MIMO_API_KEY 已配置")
        else:
            print("⚠ 可在应用设置中配置 MiMo API Key")
        
        print("\n✓ 程序初始化测试通过！")
        print("\n要启动程序，请运行：")
        print("  ./run.sh")
        print("或")
        print("  source venv/bin/activate && python3 main.py")
        
        return True
        
    except Exception as e:
        print(f"✗ 初始化失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_init()
    sys.exit(0 if success else 1)
