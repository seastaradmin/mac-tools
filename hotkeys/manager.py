"""
快捷键管理模块 — 支持长按录音（press/release）
"""

import json
import sys
from typing import Callable, Dict

from pynput import keyboard

from config import DEFAULT_HOTKEYS


FN_KEY = "<fn>"


def is_accessibility_trusted() -> bool:
    try:
        from ApplicationServices import AXIsProcessTrusted
        return bool(AXIsProcessTrusted())
    except Exception:
        return True


class MacHotkeyEventTap:
    """macOS event tap that can consume registered hotkeys."""

    KEY_CODES = {
        0: "a", 1: "s", 2: "d", 3: "f", 4: "h", 5: "g", 6: "z", 7: "x",
        8: "c", 9: "v", 11: "b", 12: "q", 13: "w", 14: "e", 15: "r",
        16: "y", 17: "t", 18: "1", 19: "2", 20: "3", 21: "4", 22: "6",
        23: "5", 25: "9", 26: "7", 28: "8", 29: "0", 31: "o", 32: "u",
        34: "i", 35: "p", 37: "l", 38: "j", 40: "k", 45: "n", 46: "m",
        49: "space", 36: "return", 48: "tab", 51: "backspace",
        53: "esc", 117: "delete",
        122: "f1", 120: "f2", 99: "f3", 118: "f4", 96: "f5", 97: "f6",
        98: "f7", 100: "f8", 101: "f9", 109: "f10", 103: "f11", 111: "f12",
    }

    def __init__(self, on_press: Callable, on_release: Callable):
        self._on_press = on_press
        self._on_release = on_release
        self._running = False
        self._run_loop = None
        self._tap = None
        self._source = None
        self._callback = None
        self._pressed_modifiers = set()
        self._modifier_masks = {}

    def start(self):
        if sys.platform != "darwin" or self._running:
            return
        try:
            import Quartz

            self._modifier_masks = {
                "<cmd>": Quartz.kCGEventFlagMaskCommand,
                "<shift>": Quartz.kCGEventFlagMaskShift,
                "<ctrl>": Quartz.kCGEventFlagMaskControl,
                "<alt>": Quartz.kCGEventFlagMaskAlternate,
                FN_KEY: Quartz.kCGEventFlagMaskSecondaryFn,
            }
            mask = (
                Quartz.CGEventMaskBit(Quartz.kCGEventKeyDown)
                | Quartz.CGEventMaskBit(Quartz.kCGEventKeyUp)
                | Quartz.CGEventMaskBit(Quartz.kCGEventFlagsChanged)
            )

            self._callback = self._handle_event
            self._tap = Quartz.CGEventTapCreate(
                Quartz.kCGSessionEventTap,
                Quartz.kCGHeadInsertEventTap,
                Quartz.kCGEventTapOptionDefault,
                mask,
                self._callback,
                None,
            )
            if self._tap is None:
                print("快捷键监听启动失败：请检查辅助功能和输入监控权限")
                return

            self._source = Quartz.CFMachPortCreateRunLoopSource(None, self._tap, 0)
            self._run_loop = Quartz.CFRunLoopGetMain()
            Quartz.CFRunLoopAddSource(self._run_loop, self._source, Quartz.kCFRunLoopCommonModes)
            Quartz.CGEventTapEnable(self._tap, True)
            self._running = True
            print("macOS 快捷键监听已启动")
        except Exception as e:
            print(f"macOS 快捷键监听失败: {e}")
            self._running = False

    def stop(self):
        self._running = False
        try:
            import Quartz

            if self._tap is not None:
                Quartz.CGEventTapEnable(self._tap, False)
            if self._run_loop is not None and self._source is not None:
                Quartz.CFRunLoopRemoveSource(
                    self._run_loop,
                    self._source,
                    Quartz.kCFRunLoopCommonModes,
                )
        except Exception:
            pass
        self._pressed_modifiers.clear()
        self._tap = None
        self._source = None
        self._run_loop = None

    def is_running(self):
        return self._running

    def _handle_event(self, proxy, event_type, event, refcon):
        import Quartz

        if event_type in (
            Quartz.kCGEventTapDisabledByTimeout,
            Quartz.kCGEventTapDisabledByUserInput,
        ):
            Quartz.CGEventTapEnable(self._tap, True)
            return event

        flags = Quartz.CGEventGetFlags(event)
        triggered = self._sync_modifier_flags(
            flags,
            sync_fn=event_type == Quartz.kCGEventFlagsChanged,
        )

        if event_type in (Quartz.kCGEventKeyDown, Quartz.kCGEventKeyUp):
            key_str = self._key_from_event(event)
            if key_str:
                if event_type == Quartz.kCGEventKeyDown:
                    triggered = self._on_press(key_str) or triggered
                else:
                    triggered = self._on_release(key_str) or triggered

        return None if triggered else event

    def _sync_modifier_flags(self, flags, sync_fn=True):
        triggered = False
        for key, mask in self._modifier_masks.items():
            if key == FN_KEY and not sync_fn:
                continue
            pressed = bool(flags & mask)
            if pressed and key not in self._pressed_modifiers:
                self._pressed_modifiers.add(key)
                triggered = self._on_press(key) or triggered
            elif not pressed and key in self._pressed_modifiers:
                self._pressed_modifiers.discard(key)
                triggered = self._on_release(key) or triggered
        return triggered

    def _key_from_event(self, event):
        import Quartz

        keycode = Quartz.CGEventGetIntegerValueField(
            event,
            Quartz.kCGKeyboardEventKeycode,
        )
        return self.KEY_CODES.get(keycode)


class HotkeyManager:
    """快捷键管理类 — 支持普通触发和长按触发两种模式"""

    def __init__(self):
        self.hotkeys: Dict[str, dict] = {}
        self.callbacks: Dict[str, Callable] = {}       # 普通触发回调
        self.press_callbacks: Dict[str, Callable] = {}  # 长按-按下回调
        self.release_callbacks: Dict[str, Callable] = {} # 长按-释放回调
        self.listener = None
        self.is_running = False

        self.current_keys = set()
        self._held_actions = set()  # 当前处于长按状态的 action
        self._triggered_actions = set()  # 普通快捷键按住期间只触发一次

        self._load_default_hotkeys()

    def _load_default_hotkeys(self):
        for action, key_str in DEFAULT_HOTKEYS.items():
            self.hotkeys[action] = {
                "key": key_str,
                "description": self._get_action_description(action)
            }

    def _get_action_description(self, action: str) -> str:
        descriptions = {"screenshot": "截图", "voice_input": "语音输入", "clipboard_history": "剪贴板历史"}
        return descriptions.get(action, action)

    def register_hotkey(self, action: str, key_str: str, callback: Callable,
                        description: str = ""):
        """注册普通快捷键（按下即触发）"""
        self.hotkeys[action] = {
            "key": key_str,
            "description": description or self._get_action_description(action)
        }
        self.callbacks[action] = callback
        if self.is_running:
            self._update_listener()

    def register_hold_hotkey(self, action: str, key_str: str,
                             on_press: Callable, on_release: Callable,
                             description: str = ""):
        """注册长按快捷键 — 按下触发 on_press，释放触发 on_release"""
        self.hotkeys[action] = {
            "key": key_str,
            "description": description or self._get_action_description(action),
            "hold": True
        }
        self.press_callbacks[action] = on_press
        self.release_callbacks[action] = on_release
        if self.is_running:
            self._update_listener()

    def unregister_hotkey(self, action: str):
        self.hotkeys.pop(action, None)
        self.callbacks.pop(action, None)
        self.press_callbacks.pop(action, None)
        self.release_callbacks.pop(action, None)
        self._held_actions.discard(action)
        self._triggered_actions.discard(action)
        self._update_listener()

    def start(self):
        if self.is_running:
            return
        self.is_running = True
        self._start_listener()
        self._update_listener()

    def stop(self):
        self.is_running = False
        if self.listener:
            self.listener.stop()
            self.listener = None

    def _start_listener(self):
        try:
            if sys.platform == "darwin":
                self.listener = MacHotkeyEventTap(
                    on_press=self._on_key_press,
                    on_release=self._on_key_release,
                )
            else:
                self.listener = keyboard.Listener(
                    on_press=self._on_key_press,
                    on_release=self._on_key_release
                )
                self.listener.daemon = True
            self.listener.start()
            if hasattr(self.listener, "is_running") and not self.listener.is_running():
                self.is_running = False
        except Exception as e:
            print(f"启动快捷键监听失败: {e}")
            self.is_running = False

    def _update_listener(self):
        pass

    def _requires_fn_listener(self):
        return any(FN_KEY in self._hotkey_parts(info.get("key", "")) for info in self.hotkeys.values())

    def _hotkey_parts(self, key_str: str):
        return {
            part.strip().lower()
            for part in key_str.split("+")
            if part.strip()
        }

    def _on_key_press(self, key):
        try:
            key_str = self._key_to_string(key)
            self.current_keys.add(key_str)
            return self._check_hotkeys_press()
        except Exception:
            return False

    def _on_key_release(self, key):
        try:
            key_str = self._key_to_string(key)
            self.current_keys.discard(key_str)
            return self._check_hotkeys_release(key_str)
        except Exception:
            return False

    def _check_hotkeys_press(self):
        """检查按下时是否匹配快捷键"""
        triggered = False
        for action, hotkey_info in self.hotkeys.items():
            key_str = hotkey_info["key"]
            required_keys = self._hotkey_parts(key_str)
            is_hold = hotkey_info.get("hold", False)

            if required_keys.issubset(self.current_keys):
                if is_hold:
                    # 长按模式：只在首次按下时触发
                    if action not in self._held_actions:
                        self._held_actions.add(action)
                        if action in self.press_callbacks:
                            try:
                                self.press_callbacks[action]()
                                triggered = True
                            except Exception as e:
                                print(f"长按回调失败: {e}")
                else:
                    # 普通模式：按住期间只触发一次，避免系统重复按键导致连发
                    if action in self.callbacks and action not in self._triggered_actions:
                        self._triggered_actions.add(action)
                        try:
                            self.callbacks[action]()
                            triggered = True
                        except Exception as e:
                            print(f"快捷键回调失败: {e}")
        return triggered

    def _check_hotkeys_release(self, released_key: str):
        """检查释放时是否触发长按快捷键的 release"""
        triggered = False
        for action in list(self._held_actions):
            hotkey_info = self.hotkeys.get(action)
            if not hotkey_info:
                continue
            key_str = hotkey_info["key"]
            required_keys = self._hotkey_parts(key_str)

            # 如果释放的键属于这个快捷键组合，触发 release
            if released_key in required_keys:
                self._held_actions.discard(action)
                if action in self.release_callbacks:
                    try:
                        self.release_callbacks[action]()
                        triggered = True
                    except Exception as e:
                        print(f"释放回调失败: {e}")

        for action in list(self._triggered_actions):
            hotkey_info = self.hotkeys.get(action)
            if not hotkey_info:
                self._triggered_actions.discard(action)
                continue
            key_str = hotkey_info["key"]
            required_keys = self._hotkey_parts(key_str)
            if released_key in required_keys:
                self._triggered_actions.discard(action)
                triggered = True
        return triggered

    def _key_to_string(self, key) -> str:
        try:
            if isinstance(key, str):
                return self._normalize_char(key)
            special_keys = {
                keyboard.Key.cmd: "<cmd>",
                keyboard.Key.cmd_l: "<cmd>",
                keyboard.Key.cmd_r: "<cmd>",
                keyboard.Key.shift: "<shift>",
                keyboard.Key.shift_l: "<shift>",
                keyboard.Key.shift_r: "<shift>",
                keyboard.Key.ctrl: "<ctrl>",
                keyboard.Key.ctrl_l: "<ctrl>",
                keyboard.Key.ctrl_r: "<ctrl>",
                keyboard.Key.alt: "<alt>",
                keyboard.Key.alt_l: "<alt>",
                keyboard.Key.alt_r: "<alt>",
            }
            if key in special_keys:
                return special_keys[key]
            if hasattr(key, 'char') and key.char:
                return self._normalize_char(key.char)
            return str(key).replace("Key.", "<") + ">"
        except Exception:
            return str(key)

    def _normalize_char(self, value: str) -> str:
        if value.lower() == FN_KEY:
            return FN_KEY
        if len(value) == 1 and 1 <= ord(value) <= 26:
            return chr(ord('a') + ord(value) - 1)
        return value.lower()

    def get_hotkeys(self) -> Dict[str, dict]:
        return self.hotkeys.copy()

    def update_hotkey(self, action: str, new_key: str):
        if action in self.hotkeys:
            self.hotkeys[action]["key"] = new_key
            if self.is_running:
                self._update_listener()

    def save_config(self, config_path: str):
        config = {
            action: {"key": info["key"], "description": info["description"]}
            for action, info in self.hotkeys.items()
        }
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)

    def load_config(self, config_path: str):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            for action, info in config.items():
                if action in self.callbacks or action in self.press_callbacks:
                    self.hotkeys[action] = info
        except Exception as e:
            print(f"加载快捷键配置失败: {e}")

    def __del__(self):
        self.stop()
