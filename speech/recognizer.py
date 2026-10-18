"""
语音识别模块 — MiMo ASR API，防崩溃设计
"""

import base64
import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional, Callable

from config import (
    MIMO_API_KEY, MIMO_BASE_URL, MIMO_ASR_MODEL,
    SUPPORTED_AUDIO_FORMATS, AUDIO_MIME_TYPES
)


class SpeechRecognizer:
    """语音识别 — 所有方法都有完整异常保护"""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or MIMO_API_KEY
        self.last_error = ""
        self.on_result_callback: Optional[Callable] = None
        self.on_error_callback: Optional[Callable] = None

    def is_available(self) -> bool:
        return bool(self.api_key)

    def recognize_file(self, audio_path: str, language: str = "zh") -> Optional[str]:
        """识别音频文件（非流式）"""
        if not self.is_available():
            self._set_error("语音识别不可用，请检查 API Key 或网络连接")
            return None

        try:
            self.last_error = ""
            data_url = self._audio_to_data_url(audio_path)
            if not data_url:
                return None

            response = self._post_chat_completion(data_url, language, stream=False)
            result = self._extract_message_content(response)
            if result:
                return result

            self._set_error("语音识别返回空结果")
            return None

        except Exception as e:
            self._set_error(f"识别请求失败: {e}")
            return None

    def recognize_stream(self, audio_path: str, language: str = "auto") -> Optional[str]:
        """流式识别 — 完整异常保护"""
        if not self.is_available():
            self._set_error("语音识别不可用，请检查 API Key 或网络连接")
            return None

        try:
            self.last_error = ""
            data_url = self._audio_to_data_url(audio_path)
            if not data_url:
                return None

            full_result = []
            for chunk in self._post_chat_completion(data_url, language, stream=True):
                try:
                    text = self._extract_delta_content(chunk)
                    if text:
                        full_result.append(text)
                        if self.on_result_callback:
                            try:
                                self.on_result_callback(text)
                            except Exception:
                                pass
                except Exception:
                    continue  # 跳过有问题的 chunk

            result = "".join(full_result)
            if result:
                return result
            self._set_error("语音识别返回空结果")
            return None

        except Exception as e:
            self._set_error(f"流式识别失败: {e}")
            return None
        finally:
            # 清理回调
            self.on_result_callback = None

    def _audio_to_data_url(self, audio_path: str) -> Optional[str]:
        """将音频文件转为 data URL"""
        try:
            path = Path(audio_path)
            if not path.exists():
                self._set_error("录音文件不存在")
                return None

            ext = path.suffix[1:].lower()
            if ext not in SUPPORTED_AUDIO_FORMATS:
                self._set_error(f"不支持的音频格式: {ext or 'unknown'}")
                return None

            with open(audio_path, "rb") as f:
                audio_bytes = f.read()

            if len(audio_bytes) == 0:
                self._set_error("录音文件为空")
                return None

            audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
            mime = AUDIO_MIME_TYPES.get(ext, "audio/wav")
            return f"data:{mime};base64,{audio_b64}"

        except Exception as e:
            self._set_error(f"音频编码失败: {e}")
            return None

    def _post_chat_completion(self, data_url: str, language: str, stream: bool):
        payload = {
            "model": MIMO_ASR_MODEL,
            "messages": [{
                "role": "user",
                "content": [{
                    "type": "input_audio",
                    "input_audio": {"data": data_url},
                }],
            }],
            "asr_options": {"language": language},
            "stream": stream,
        }
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            self._chat_completions_url(),
            data=data,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                if stream:
                    return list(self._iter_sse_chunks(response))
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"HTTP {e.code}: {body[:200]}") from e
        except urllib.error.URLError as e:
            raise RuntimeError(str(e.reason)) from e

    def _chat_completions_url(self) -> str:
        return f"{MIMO_BASE_URL.rstrip('/')}/chat/completions"

    def _iter_sse_chunks(self, response):
        for raw_line in response:
            line = raw_line.decode("utf-8", errors="replace").strip()
            if not line or not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                break
            try:
                yield json.loads(data)
            except json.JSONDecodeError:
                continue

    def _extract_message_content(self, response) -> Optional[str]:
        try:
            choices = response.get("choices") or []
            message = choices[0].get("message") or {}
            content = message.get("content")
            return content if content else None
        except Exception:
            return None

    def _extract_delta_content(self, chunk) -> Optional[str]:
        try:
            choices = chunk.get("choices") or []
            delta = choices[0].get("delta") or {}
            content = delta.get("content")
            return content if content else None
        except Exception:
            return None

    def get_last_error(self) -> str:
        return self.last_error

    def _set_error(self, message: str):
        self.last_error = message
        print(f"[ASR] {message}")

    def set_on_result_callback(self, callback):
        self.on_result_callback = callback

    def set_on_error_callback(self, callback):
        self.on_error_callback = callback
