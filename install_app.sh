#!/bin/bash
#
# Cleanly install the packaged app into /Applications.
#

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

APP_SOURCE="dist/Mac截图语音工具.app"
APP_TARGET="/Applications/Mac截图语音工具.app"
APP_PROCESS="$APP_TARGET/Contents/MacOS/Mac截图语音工具"

if [ ! -d "$APP_SOURCE" ]; then
    echo "错误: 未找到 $APP_SOURCE，请先运行 ./build_app.sh"
    exit 1
fi

pkill -f "$APP_PROCESS" >/dev/null 2>&1 || true

# Remove the old bundle first. Copying over an existing .app can leave stale
# framework files from older builds inside the target bundle.
rm -rf "$APP_TARGET"
ditto "$APP_SOURCE" "$APP_TARGET"
xattr -cr "$APP_TARGET" >/dev/null 2>&1 || true

echo "已安装: $APP_TARGET"
du -sh "$APP_TARGET"

open "$APP_TARGET"
