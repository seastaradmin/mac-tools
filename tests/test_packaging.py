import unittest
import re
from pathlib import Path

from app_metadata import APP_BUNDLE_IDENTIFIER, APP_BUNDLE_NAME, APP_VERSION


class PackagingTests(unittest.TestCase):

    def test_default_requirements_exclude_large_optional_packages(self):
        requirements = Path("requirements.txt").read_text(encoding="utf-8")

        self.assertNotIn("torch", requirements)
        self.assertNotIn("transformers", requirements)
        self.assertNotIn("opencv-python", requirements)
        self.assertNotIn("openai", requirements)
        self.assertNotIn("numpy", requirements)

    def test_spec_excludes_large_optional_hidden_imports(self):
        spec = Path("Mac截图语音工具.spec").read_text(encoding="utf-8")
        hiddenimports = re.search(
            r"hiddenimports=\[(.*?)\],",
            spec,
            flags=re.DOTALL,
        ).group(1)
        excludes = re.search(
            r"excludes=\[(.*?)\],",
            spec,
            flags=re.DOTALL,
        ).group(1)

        self.assertNotIn("'torch'", hiddenimports)
        self.assertNotIn("'transformers'", hiddenimports)
        self.assertNotIn("'cv2'", hiddenimports)
        self.assertNotIn("'openai'", hiddenimports)
        self.assertNotIn("'numpy'", hiddenimports)
        self.assertIn("'torch'", excludes)
        self.assertIn("'transformers'", excludes)
        self.assertIn("'cv2'", excludes)
        self.assertIn("'openai'", excludes)
        self.assertIn("'numpy'", excludes)

    def test_spec_keeps_macos_dynamic_imports(self):
        spec = Path("Mac截图语音工具.spec").read_text(encoding="utf-8")

        self.assertIn("'ApplicationServices'", spec)
        self.assertIn("'AppKit'", spec)
        self.assertIn("'Foundation'", spec)
        self.assertIn("'Quartz'", spec)
        self.assertIn("'objc'", spec)

    def test_spec_uses_shared_app_metadata(self):
        spec = Path("Mac截图语音工具.spec").read_text(encoding="utf-8")
        main = Path("main.py").read_text(encoding="utf-8")

        self.assertIn("from app_metadata import", spec)
        self.assertIn("sys.path.insert", spec)
        self.assertIn("'LSUIElement': True", spec)
        self.assertIn("APP_VERSION", spec)
        self.assertIn("APP_BUNDLE_NAME", spec)
        self.assertIn("APP_BUNDLE_IDENTIFIER", spec)
        self.assertIn("APP_VERSION", main)
        self.assertEqual(APP_VERSION, "3.0.0")
        self.assertEqual(APP_BUNDLE_NAME, "Mac截图语音工具")
        self.assertEqual(APP_BUNDLE_IDENTIFIER, "com.mactools.screenshot-voice")

    def test_local_test_keeps_menu_bar_accessory_mode(self):
        main = Path("main.py").read_text(encoding="utf-8")

        self.assertIn("NSApplicationActivationPolicyAccessory", main)
        self.assertIn("setActivationPolicy_(NSApplicationActivationPolicyAccessory)", main)
        self.assertNotIn("NSApplicationActivationPolicyRegular", main)

    def test_spec_filters_unused_qt_release_files(self):
        spec = Path("Mac截图语音工具.spec").read_text(encoding="utf-8")

        self.assertIn("keep_release_file", spec)
        self.assertIn("'PyQt6/Qt6/lib/QtPdf.framework'", spec)
        self.assertIn("'PyQt6/Qt6/plugins/platforms/libqminimal.dylib'", spec)
        self.assertIn("'PyQt6/Qt6/plugins/platforms/libqoffscreen.dylib'", spec)
        self.assertIn("release_binaries", spec)
        self.assertIn("release_datas", spec)

    def test_spec_does_not_copy_source_package_directories_as_data(self):
        spec = Path("Mac截图语音工具.spec").read_text(encoding="utf-8")
        datas = re.search(
            r"datas=\[(.*?)\],",
            spec,
            flags=re.DOTALL,
        ).group(1)

        self.assertIn("('config.py', '.')", datas)
        self.assertIn("('app_metadata.py', '.')", datas)
        self.assertNotIn("('ui', 'ui')", datas)
        self.assertNotIn("('polish', 'polish')", datas)
        self.assertNotIn("('screenshot', 'screenshot')", datas)
        self.assertNotIn("('speech', 'speech')", datas)
        self.assertNotIn("('hotkeys', 'hotkeys')", datas)

    def test_main_window_does_not_import_optional_polish_module(self):
        main_window = Path("ui/main_window.py").read_text(encoding="utf-8")

        self.assertNotIn("TextPolisher", main_window)
        self.assertNotIn("PolishThread", main_window)

    def test_native_voice_ball_is_opt_in(self):
        main_window = Path("ui/main_window.py").read_text(encoding="utf-8")

        self.assertIn("def should_use_native_voice_ball()", main_window)
        self.assertIn('os.environ.get("MAC_TOOLS_USE_NATIVE_VOICE_BALL") == "1"', main_window)
        self.assertIn("self._record_indicator = RecordingIndicator()", main_window)

    def test_import_smoke_does_not_require_optional_polish_module(self):
        smoke = Path("test_imports.py").read_text(encoding="utf-8")

        self.assertNotIn("TextPolisher", smoke)
        self.assertNotIn("polish.polisher", smoke)
        self.assertIn("app_diagnostics", smoke)
        self.assertIn("macos_permissions", smoke)

    def test_init_smoke_uses_current_api_key_guidance(self):
        smoke = Path("test_init.py").read_text(encoding="utf-8")

        self.assertIn("应用设置中配置 MiMo API Key", smoke)
        self.assertNotIn("语音识别功能将不可用", smoke)

    def test_build_script_is_non_interactive_by_default(self):
        script = Path("build_app.sh").read_text(encoding="utf-8")

        self.assertNotIn("read -p", script)
        self.assertNotIn("系统偏好设置", script)
        self.assertIn("--open", script)
        self.assertIn("应用设置中配置", script)
        self.assertIn("系统设置 > 隐私与安全", script)
        self.assertIn("权限设置", script)

    def test_run_script_skips_dependency_install_when_requirements_unchanged(self):
        script = Path("run.sh").read_text(encoding="utf-8")

        self.assertIn("set -e", script)
        self.assertIn("REQ_STAMP=\"venv/.requirements.sha256\"", script)
        self.assertIn("shasum -a 256 requirements.txt", script)
        self.assertIn("依赖已就绪，跳过安装", script)
        self.assertIn("python3 -m pip install -r requirements.txt -q", script)
        self.assertIn("应用设置中配置 MiMo API Key", script)
        self.assertNotIn("语音识别功能将不可用", script)

    def test_dmg_script_builds_compact_non_interactive_image(self):
        script = Path("create_dmg.sh").read_text(encoding="utf-8")

        self.assertNotIn("read -p", script)
        self.assertIn("trap cleanup EXIT", script)
        self.assertIn("-fs HFS+", script)
        self.assertIn("-format UDBZ", script)
        self.assertIn("--open", script)
        self.assertIn("ditto", script)

    def test_install_script_removes_old_bundle_before_copying(self):
        script = Path("install_app.sh").read_text(encoding="utf-8")

        self.assertIn("APP_TARGET=\"/Applications/Mac截图语音工具.app\"", script)
        self.assertIn("pkill -f \"$APP_PROCESS\"", script)
        self.assertIn("rm -rf \"$APP_TARGET\"", script)
        self.assertIn("ditto \"$APP_SOURCE\" \"$APP_TARGET\"", script)
        self.assertIn("xattr -cr \"$APP_TARGET\"", script)
        self.assertIn("open \"$APP_TARGET\"", script)

    def test_local_test_script_removes_installed_app_before_opening_dist(self):
        script = Path("test_local_app.sh").read_text(encoding="utf-8")

        self.assertIn("LOCAL_APP=\"$SCRIPT_DIR/dist/Mac截图语音工具.app\"", script)
        self.assertIn("INSTALLED_APP=\"/Applications/Mac截图语音工具.app\"", script)
        self.assertIn("pkill -f \"$LOCAL_PROCESS\"", script)
        self.assertIn("pkill -f \"$INSTALLED_PROCESS\"", script)
        self.assertIn("rm -rf \"$INSTALLED_APP\"", script)
        self.assertIn("\"${1:-}\" = \"--rebuild\"", script)
        self.assertIn("[ ! -d \"$LOCAL_APP\" ]", script)
        self.assertIn("复用现有本地测试版本", script)
        self.assertIn("open -n \"$LOCAL_APP\" --args --local-test", script)

    def test_app_prompts_for_hotkey_permissions_at_startup(self):
        main_window = Path("ui/main_window.py").read_text(encoding="utf-8")

        self.assertIn("def _show_hotkey_permissions_setup(self):", main_window)
        self.assertIn("全局快捷键需要开启辅助功能和输入监控权限", main_window)
        self.assertIn("打开输入监控设置", main_window)
        self.assertIn("QTimer.singleShot(500, self._show_hotkey_permissions_setup)", main_window)

    def test_screenshot_failure_prompts_for_screen_recording(self):
        main_window = Path("ui/main_window.py").read_text(encoding="utf-8")

        self.assertIn("def _show_screen_recording_setup(self):", main_window)
        self.assertIn("截图功能需要开启屏幕录制权限", main_window)
        self.assertIn("打开屏幕录制设置", main_window)
        self.assertIn("self._show_screen_recording_setup()", main_window)

    def test_release_check_covers_shipping_gates(self):
        script = Path("release_check.sh").read_text(encoding="utf-8")

        self.assertIn("python test_imports.py", script)
        self.assertIn("python test_init.py", script)
        self.assertIn("python -m unittest", script)
        self.assertIn("./build_app.sh", script)
        self.assertIn("APP_MAX_MB=120", script)
        self.assertIn("DMG_MAX_MB=50", script)
        self.assertIn("forbidden = {\"numpy\", \"openai\", \"torch\", \"transformers\", \"polish.polisher\"}", script)
        self.assertIn("\"$APP_BIN\" > \"$SMOKE_LOG\" 2>&1 &", script)
        self.assertIn("./create_dmg.sh", script)
        self.assertIn("hdiutil attach", script)
        self.assertIn("test -L \"$MOUNT_DIR/Applications\"", script)
        self.assertIn("pkill -f \"Mac截图语音工具.app/Contents/MacOS/Mac截图语音工具\"", script)

    def test_docs_do_not_pin_stale_package_sizes_or_removed_dependencies(self):
        docs = (
            Path("README.md").read_text(encoding="utf-8")
            + Path("启动说明.txt").read_text(encoding="utf-8")
            + Path("打包说明.md").read_text(encoding="utf-8")
            + Path("问题解决.md").read_text(encoding="utf-8")
        )

        self.assertNotIn("645MB", docs)
        self.assertNotIn("271MB", docs)
        self.assertNotIn("OpenCV", docs)
        self.assertNotIn("OpenAI", docs)
        self.assertNotIn("PyTorch", docs)
        self.assertNotIn("Transformers", docs)

    def test_project_does_not_contain_embedded_service_tokens(self):
        searchable_paths = [
            "config.py",
            "user_config.json",
            "README.md",
            "启动说明.txt",
            "打包说明.md",
            "问题解决.md",
            "build_app.sh",
            "run.sh",
            "release_check.sh",
        ]
        combined = "\n".join(
            Path(path).read_text(encoding="utf-8") for path in searchable_paths
        )

        self.assertNotIn("tp-", combined)

    def test_docs_match_current_voice_and_permission_flows(self):
        docs = (
            Path("README.md").read_text(encoding="utf-8")
            + Path("启动说明.txt").read_text(encoding="utf-8")
            + Path("打包说明.md").read_text(encoding="utf-8")
            + Path("问题解决.md").read_text(encoding="utf-8")
        )

        self.assertNotIn("文字润色", docs)
        self.assertNotIn("开始/停止录音", docs)
        self.assertNotIn("系统偏好设置", docs)
        self.assertIn("长按录音", docs)
        self.assertIn("系统设置 > 隐私与安全", docs)
        self.assertIn("运行诊断", docs)
        self.assertIn("./install_app.sh", docs)
        self.assertIn("./release_check.sh", docs)


if __name__ == "__main__":
    unittest.main()
