#!/bin/bash
#
# 解决macOS应用无法打开的问题
#

set -e

echo "=========================================="
echo "   修复Mac应用问题"
echo "=========================================="
echo ""

APP_PATH="dist/Mac截图语音工具.app"

# 检查应用是否存在
if [ ! -d "$APP_PATH" ]; then
    echo "错误: 未找到应用文件"
    exit 1
fi

echo "步骤1: 移除隔离标记（解决Gatekeeper阻止问题）..."
xattr -cr "$APP_PATH"
echo "✓ 隔离标记已移除"

echo ""
echo "步骤2: 重新签名应用..."
codesign --force --deep --sign - "$APP_PATH"
echo "✓ 应用已重新签名"

echo ""
echo "=========================================="
echo "   修复完成！"
echo "=========================================="
echo ""
echo "现在可以双击打开应用了"
echo ""
echo "如果仍然无法打开，请尝试："
echo "  1. 右键点击应用，选择'打开'"
echo "  2. 在弹出的对话框中点击'打开'"
echo ""
