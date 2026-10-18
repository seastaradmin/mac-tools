#!/bin/bash
#
# Run only the local dist app for testing.
#

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

LOCAL_APP="$SCRIPT_DIR/dist/Mac截图语音工具.app"
LOCAL_PROCESS="$LOCAL_APP/Contents/MacOS/Mac截图语音工具"
INSTALLED_APP="/Applications/Mac截图语音工具.app"
INSTALLED_PROCESS="$INSTALLED_APP/Contents/MacOS/Mac截图语音工具"
REBUILD=0
DID_REBUILD=0

if [ "${1:-}" = "--rebuild" ]; then
    REBUILD=1
fi

pkill -f "$LOCAL_PROCESS" >/dev/null 2>&1 || true
pkill -f "$INSTALLED_PROCESS" >/dev/null 2>&1 || true

if [ -d "$INSTALLED_APP" ]; then
    rm -rf "$INSTALLED_APP"
    echo "已移除 Applications 中的旧版本，避免本地测试冲突"
fi

if [ "$REBUILD" -eq 1 ] || [ ! -d "$LOCAL_APP" ]; then
    DID_REBUILD=1
    ./build_app.sh
    ./reset_permissions.sh --no-open
else
    echo "复用现有本地测试版本，避免反复重置 macOS 权限"
    echo "如需重新打包，请运行: ./test_local_app.sh --rebuild"
fi

xattr -cr "$LOCAL_APP" >/dev/null 2>&1 || true

echo "启动本地测试版本: $LOCAL_APP"
echo "截图需允许 屏幕录制；全局快捷键需允许 辅助功能和输入监控；粘贴需允许 辅助功能"
if [ "$DID_REBUILD" -eq 1 ]; then
    echo "已重置旧 TCC 权限记录；请在系统设置中重新勾选权限"
fi
open -n "$LOCAL_APP" --args --local-test
