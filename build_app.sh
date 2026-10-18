#!/bin/bash
#
# Mac应用打包脚本
#

set -e

echo "=========================================="
echo "   Mac截图语音工具 - 打包脚本"
echo "=========================================="
echo "用法: ./build_app.sh [--open]"
echo ""

OPEN_AFTER_BUILD=0
if [ "${1:-}" = "--open" ]; then
    OPEN_AFTER_BUILD=1
fi

# 获取脚本所在目录
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# 检查虚拟环境
if [ ! -d "venv" ]; then
    echo "错误: 未找到虚拟环境，请先运行 ./run.sh 安装依赖"
    exit 1
fi

# 激活虚拟环境
source venv/bin/activate

# 检查PyInstaller是否安装
if ! pip show pyinstaller > /dev/null 2>&1; then
    echo "正在安装PyInstaller..."
    pip install pyinstaller -q
fi

# 清理旧的构建文件
echo "清理旧的构建文件..."
rm -rf build dist

# 生成应用图标
echo "检查应用图标..."
if [ ! -f "icon.icns" ]; then
    echo "未找到图标文件，将使用默认图标"
fi

# 执行打包
echo ""
echo "开始打包..."
echo "这可能需要几分钟时间，请耐心等待..."
echo ""

pyinstaller "Mac截图语音工具.spec" \
    --noconfirm \
    --clean \
    --distpath dist \
    --workpath build

# 检查打包结果
if [ -d "dist/Mac截图语音工具.app" ]; then
    echo ""
    echo "=========================================="
    echo "   打包成功！"
    echo "=========================================="
    echo ""
    echo "应用位置: dist/Mac截图语音工具.app"
    echo ""
    echo "使用方法:"
    echo "  1. 将应用拖到 Applications 文件夹"
    echo "  2. 首次运行需要授予以下权限:"
    echo "     - 屏幕录制权限"
    echo "     - 麦克风权限"
    echo "     - 辅助功能权限"
    echo "     - 输入监控权限"
    echo ""
    echo "注意事项:"
    echo "  - 如果遇到权限问题，可从托盘菜单打开“权限设置”"
    echo "  - 也可手动进入 系统设置 > 隐私与安全"
    echo "  - 语音识别 API Key 可在应用设置中配置，也可用 MIMO_API_KEY 环境变量覆盖"
    echo "  - 如需构建后立即打开应用，请运行: ./build_app.sh --open"
    echo ""
    
    if [ "$OPEN_AFTER_BUILD" -eq 1 ]; then
        open "dist/Mac截图语音工具.app"
    fi
else
    echo ""
    echo "=========================================="
    echo "   打包失败！"
    echo "=========================================="
    echo ""
    echo "请检查错误信息并重试"
    exit 1
fi
