#!/bin/bash
#
# Release verification: tests, packaging, size checks, smoke run, DMG mount.
#

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

APP_PATH="dist/Mac截图语音工具.app"
APP_BIN="$APP_PATH/Contents/MacOS/Mac截图语音工具"
DMG_PATH="Mac截图语音工具.dmg"
APP_MAX_MB=120
DMG_MAX_MB=50
SMOKE_LOG="temp/release_app.log"

APP_PID=""
MOUNT_DIR=""

cleanup() {
    if [ -n "$APP_PID" ] && kill -0 "$APP_PID" >/dev/null 2>&1; then
        kill "$APP_PID" >/dev/null 2>&1 || true
        wait "$APP_PID" >/dev/null 2>&1 || true
    fi
    pkill -f "Mac截图语音工具.app/Contents/MacOS/Mac截图语音工具" >/dev/null 2>&1 || true
    if [ -n "$MOUNT_DIR" ] && mount | grep -q "$MOUNT_DIR"; then
        hdiutil detach "$MOUNT_DIR" >/dev/null 2>&1 || true
    fi
    if [ -n "$MOUNT_DIR" ] && [ -d "$MOUNT_DIR" ]; then
        rmdir "$MOUNT_DIR" >/dev/null 2>&1 || true
    fi
}
trap cleanup EXIT

echo "=========================================="
echo "   Mac截图语音工具 - Release Check"
echo "=========================================="

if [ ! -d "venv" ]; then
    echo "错误: 未找到虚拟环境，请先运行 ./run.sh"
    exit 1
fi

source venv/bin/activate

echo ""
echo "1/8 运行源码 smoke..."
python test_imports.py
python test_init.py

echo ""
echo "2/8 运行单元测试..."
python -m unittest \
    tests.test_main_window_flows \
    tests.test_app_diagnostics \
    tests.test_macos_permissions \
    tests.test_config_paths \
    tests.test_packaging \
    tests.test_recognizer \
    tests.test_voice_input \
    tests.test_screenshot_capture \
    tests.test_recorder \
    tests.test_hotkeys

echo ""
echo "3/8 构建 .app..."
./build_app.sh

if [ ! -x "$APP_BIN" ]; then
    echo "错误: 未找到可执行文件 $APP_BIN"
    exit 1
fi

echo ""
echo "4/8 检查 .app 体积..."
APP_SIZE_MB=$(du -sm "$APP_PATH" | awk '{print $1}')
echo "应用大小: ${APP_SIZE_MB}MB"
if [ "$APP_SIZE_MB" -gt "$APP_MAX_MB" ]; then
    echo "错误: 应用超过 ${APP_MAX_MB}MB"
    exit 1
fi

echo ""
echo "5/8 检查打包依赖..."
python - <<'PY'
from PyInstaller.archive.readers import ZlibArchiveReader

archive = ZlibArchiveReader("build/Mac截图语音工具/PYZ-00.pyz")
mods = set(archive.toc.keys())
required = {"app_diagnostics", "macos_permissions", "Quartz"}
forbidden = {"numpy", "openai", "torch", "transformers", "polish.polisher"}

missing = sorted(required - mods)
present = sorted(forbidden & mods)
if missing:
    raise SystemExit(f"missing required modules: {missing}")
if present:
    raise SystemExit(f"unexpected heavy modules in package: {present}")
print("依赖检查通过")
PY

echo ""
echo "6/8 打包应用烟测..."
mkdir -p temp
"$APP_BIN" > "$SMOKE_LOG" 2>&1 &
APP_PID=$!
sleep 5
if ! kill -0 "$APP_PID" >/dev/null 2>&1; then
    echo "错误: 打包应用启动后提前退出"
    cat "$SMOKE_LOG" || true
    exit 1
fi
kill "$APP_PID" >/dev/null 2>&1 || true
wait "$APP_PID" >/dev/null 2>&1 || true
APP_PID=""
echo "烟测通过"

echo ""
echo "7/8 创建并检查 DMG..."
./create_dmg.sh
DMG_SIZE_MB=$(du -sm "$DMG_PATH" | awk '{print $1}')
echo "DMG大小: ${DMG_SIZE_MB}MB"
if [ "$DMG_SIZE_MB" -gt "$DMG_MAX_MB" ]; then
    echo "错误: DMG 超过 ${DMG_MAX_MB}MB"
    exit 1
fi
hdiutil imageinfo "$DMG_PATH" | grep -q "Format: UDBZ"

echo ""
echo "8/8 挂载验证 DMG 内容..."
MOUNT_DIR=$(mktemp -d)
hdiutil attach "$DMG_PATH" -readonly -nobrowse -mountpoint "$MOUNT_DIR"
test -d "$MOUNT_DIR/Mac截图语音工具.app"
test -L "$MOUNT_DIR/Applications"
hdiutil detach "$MOUNT_DIR"
rmdir "$MOUNT_DIR"
MOUNT_DIR=""

if pgrep -fl "Mac截图语音工具|python main.py" >/dev/null 2>&1; then
    echo "错误: 检测到残留应用进程"
    pgrep -fl "Mac截图语音工具|python main.py" || true
    exit 1
fi

echo ""
echo "=========================================="
echo "   Release Check 通过"
echo "=========================================="
du -sh "$APP_PATH" "$DMG_PATH"
