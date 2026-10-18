#!/bin/bash
#
# Reset local macOS privacy state for the development build.
#
# This cannot grant permissions automatically. macOS requires the user to
# approve Accessibility, Input Monitoring, and Screen Recording in System Settings.
#

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

APP_NAME="Mac截图语音工具"
BUNDLE_ID="com.mactools.screenshot-voice"
LOCAL_APP="$SCRIPT_DIR/dist/$APP_NAME.app"
LOCAL_PROCESS="$LOCAL_APP/Contents/MacOS/$APP_NAME"
INSTALLED_APP="/Applications/$APP_NAME.app"
INSTALLED_PROCESS="$INSTALLED_APP/Contents/MacOS/$APP_NAME"
DMG_APP="/Volumes/$APP_NAME/$APP_NAME.app"
LSREGISTER="/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister"
OPEN_APP=1

for arg in "$@"; do
    case "$arg" in
        --no-open)
            OPEN_APP=0
            ;;
        *)
            echo "未知参数: $arg"
            echo "用法: ./reset_permissions.sh [--no-open]"
            exit 1
            ;;
    esac
done

echo "停止正在运行的 $APP_NAME..."
pkill -f "$LOCAL_PROCESS" >/dev/null 2>&1 || true
pkill -f "$INSTALLED_PROCESS" >/dev/null 2>&1 || true
pkill -f "$APP_NAME.app/Contents/MacOS/$APP_NAME" >/dev/null 2>&1 || true

if [ -d "$INSTALLED_APP" ]; then
    echo "移除 /Applications 中的旧版本..."
    rm -rf "$INSTALLED_APP"
fi

echo "清理 LaunchServices 旧注册..."
"$LSREGISTER" -u "$DMG_APP" >/dev/null 2>&1 || true
"$LSREGISTER" -u "$INSTALLED_APP" >/dev/null 2>&1 || true
if [ -d "$LOCAL_APP" ]; then
    "$LSREGISTER" -u "$LOCAL_APP" >/dev/null 2>&1 || true
    "$LSREGISTER" -f "$LOCAL_APP" >/dev/null 2>&1 || true
fi
"$LSREGISTER" -kill -r -domain user >/dev/null 2>&1 || true

echo "重置 TCC 权限记录..."
tccutil reset Accessibility "$BUNDLE_ID" >/dev/null 2>&1 || true
tccutil reset ListenEvent "$BUNDLE_ID" >/dev/null 2>&1 || true
tccutil reset ScreenCapture "$BUNDLE_ID" >/dev/null 2>&1 || true
tccutil reset Microphone "$BUNDLE_ID" >/dev/null 2>&1 || true

echo ""
echo "已完成清理。macOS 不允许脚本自动授予这些权限。"
echo "接下来请在系统设置中重新勾选 ${APP_NAME}:"
echo "  1. 隐私与安全 > 辅助功能"
echo "  2. 隐私与安全 > 输入监控"
echo "  3. 隐私与安全 > 屏幕录制"
echo "  4. 首次录音时允许麦克风"
echo ""

open "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility" || true

if [ "$OPEN_APP" -eq 1 ] && [ -d "$LOCAL_APP" ]; then
    echo "启动本地测试版本..."
    open -n "$LOCAL_APP" --args --local-test
elif [ "$OPEN_APP" -eq 0 ]; then
    echo "已跳过启动应用。请通过 ./test_local_app.sh 启动本地测试版本。"
else
    echo "未找到 $LOCAL_APP。请先运行 ./test_local_app.sh --rebuild"
fi
