import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from speech.recognizer import SpeechRecognizer


class FakeResponse:
    def __init__(self, body=None, lines=None):
        self.body = body or b""
        self.lines = lines or []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return self.body

    def __iter__(self):
        return iter(self.lines)


class SpeechRecognizerTests(unittest.TestCase):

    def make_recognizer(self):
        recognizer = SpeechRecognizer.__new__(SpeechRecognizer)
        recognizer.api_key = "key"
        recognizer.last_error = ""
        recognizer.on_result_callback = None
        recognizer.on_error_callback = None
        return recognizer

    def test_missing_audio_file_sets_last_error(self):
        recognizer = self.make_recognizer()

        with redirect_stdout(StringIO()):
            result = recognizer.recognize_file("/tmp/does-not-exist.wav")

        self.assertIsNone(result)
        self.assertEqual(recognizer.get_last_error(), "录音文件不存在")

    def test_empty_audio_file_sets_last_error(self):
        recognizer = self.make_recognizer()

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "empty.wav"
            path.write_bytes(b"")

            with redirect_stdout(StringIO()):
                result = recognizer.recognize_file(str(path))

        self.assertIsNone(result)
        self.assertEqual(recognizer.get_last_error(), "录音文件为空")

    def test_unsupported_audio_format_sets_last_error(self):
        recognizer = self.make_recognizer()

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "audio.aiff"
            path.write_bytes(b"data")

            with redirect_stdout(StringIO()):
                result = recognizer.recognize_file(str(path))

        self.assertIsNone(result)
        self.assertEqual(recognizer.get_last_error(), "不支持的音频格式: aiff")

    def test_request_exception_sets_last_error(self):
        recognizer = self.make_recognizer()

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "audio.wav"
            path.write_bytes(b"data")

            with patch("speech.recognizer.urllib.request.urlopen", side_effect=RuntimeError("network down")), \
                 redirect_stdout(StringIO()):
                result = recognizer.recognize_file(str(path))

        self.assertIsNone(result)
        self.assertEqual(recognizer.get_last_error(), "识别请求失败: network down")

    def test_recognize_file_posts_minimal_chat_completion_request(self):
        recognizer = self.make_recognizer()
        body = json.dumps({
            "choices": [{"message": {"content": "你好"}}]
        }).encode("utf-8")
        captured = {}

        def fake_urlopen(request, timeout):
            captured["url"] = request.full_url
            captured["headers"] = dict(request.header_items())
            captured["payload"] = json.loads(request.data.decode("utf-8"))
            captured["timeout"] = timeout
            return FakeResponse(body=body)

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "audio.wav"
            path.write_bytes(b"data")

            with patch("speech.recognizer.urllib.request.urlopen", side_effect=fake_urlopen), \
                 redirect_stdout(StringIO()):
                result = recognizer.recognize_file(str(path), language="zh")

        self.assertEqual(result, "你好")
        self.assertEqual(captured["url"], "https://token-plan-cn.xiaomimimo.com/v1/chat/completions")
        self.assertEqual(captured["timeout"], 30)
        self.assertEqual(captured["headers"]["Authorization"], "Bearer key")
        self.assertEqual(captured["payload"]["model"], "mimo-v2.5-asr")
        self.assertEqual(captured["payload"]["asr_options"]["language"], "zh")
        self.assertFalse(captured["payload"]["stream"])
        self.assertIn("data:audio/wav;base64,", captured["payload"]["messages"][0]["content"][0]["input_audio"]["data"])

    def test_recognize_stream_parses_sse_chunks(self):
        recognizer = self.make_recognizer()
        chunks = [
            'data: {"choices":[{"delta":{"content":"你"}}]}\n'.encode("utf-8"),
            'data: {"choices":[{"delta":{"content":"好"}}]}\n'.encode("utf-8"),
            b"data: [DONE]\n",
        ]

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "audio.wav"
            path.write_bytes(b"data")

            with patch("speech.recognizer.urllib.request.urlopen", return_value=FakeResponse(lines=chunks)), \
                 redirect_stdout(StringIO()):
                result = recognizer.recognize_stream(str(path), language="zh")

        self.assertEqual(result, "你好")


if __name__ == "__main__":
    unittest.main()
