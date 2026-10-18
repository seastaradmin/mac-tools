#!/bin/bash
#
# 创建DMG安装包
#

set -e

echo "=========================================="
echo "   创建DMG安装包"
echo "=========================================="
echo ""

# 获取脚本所在目录
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

OPEN_AFTER_BUILD=false
if [ "${1:-}" = "--open" ]; then
    OPEN_AFTER_BUILD=true
fi

APP_PATH="dist/Mac截图语音工具.app"
DMG_NAME="Mac截图语音工具.dmg"
VOLUME_NAME="Mac截图语音工具"

# 检查应用是否存在
if [ ! -d "$APP_PATH" ]; then
    echo "错误: 未找到应用文件，请先运行 build_app.sh"
    exit 1
fi

# 创建临时目录
TEMP_DIR=$(mktemp -d)
cleanup() {
    rm -rf "$TEMP_DIR"
}
trap cleanup EXIT

echo "创建临时目录: $TEMP_DIR"

# 复制应用到临时目录
echo "复制应用..."
ditto "$APP_PATH" "$TEMP_DIR/Mac截图语音工具.app"

# 创建Applications链接
ln -s /Applications "$TEMP_DIR/Applications"

# 创建DMG
echo "创建DMG文件..."
hdiutil create -volname "$VOLUME_NAME" \
    -srcfolder "$TEMP_DIR" \
    -fs HFS+ \
    -ov -format UDBZ \
    "$DMG_NAME"

# 检查结果
if [ -f "$DMG_NAME" ]; then
    DMG_SIZE=$(du -sh "$DMG_NAME" | cut -f1)
    APP_SIZE=$(du -sh "$APP_PATH" | cut -f1)
    echo ""
    echo "=========================================="
    echo "   DMG创建成功！"
    echo "=========================================="
    echo ""
    echo "DMG文件: $DMG_NAME"
    echo "应用大小: $APP_SIZE"
    echo "文件大小: $DMG_SIZE"
    echo ""
    echo "使用方法:"
    echo "  1. 双击 $DMG_NAME 打开"
    echo "  2. 将应用拖到 Applications 文件夹"
    echo "  3. 从 Applications 或 Launchpad 启动应用"
    echo ""
    if [ "$OPEN_AFTER_BUILD" = true ]; then
        open "$DMG_NAME"
    fi
else
    echo ""
    echo "=========================================="
    echo "   DMG创建失败！"
    echo "=========================================="
    echo ""
    exit 1
fi
