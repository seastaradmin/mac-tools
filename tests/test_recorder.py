import unittest
from contextlib import redirect_stdout
from io import StringIO
from array import array
from unittest.mock import patch


class FakeStream:
    def __init__(self, read_error=None):
        self.closed = False
        self.stopped = False
        self.active = True
        self.read_error = read_error

    def is_active(self):
        return self.active

    def stop_stream(self):
        self.stopped = True
        self.active = False

    def close(self):
        self.closed = True

    def read(self, *_args, **_kwargs):
        if self.read_error:
            raise self.read_error
        return b"\x00\x00" * 1024


class FakePyAudio:
    def __init__(self, stream=None, error=None):
        self.stream = stream or FakeStream()
        self.error = error
        self.terminated = False

    def open(self, **_kwargs):
        if self.error:
            raise self.error
        return self.stream

    def get_sample_size(self, _format):
        return 2

    def terminate(self):
        self.terminated = True


class AudioRecorderTests(unittest.TestCase):

    def test_start_failure_leaves_recorder_idle(self):
        fake_audio = FakePyAudio(error=OSError("no microphone"))
        with patch("speech.recorder.pyaudio.PyAudio", return_value=fake_audio):
            from speech.recorder import AudioRecorder

            recorder = AudioRecorder()
            with self.assertRaises(OSError):
                recorder.start_recording("/tmp/test.wav")

            self.assertFalse(recorder.is_recording)
            self.assertIsNone(recorder.stream)
            self.assertIsNone(recorder.output_path)
            self.assertEqual(recorder.frames, [])

    def test_stop_closes_stream_and_clears_thread_reference(self):
        stream = FakeStream(read_error=OSError("read stopped"))
        fake_audio = FakePyAudio(stream=stream)
        with patch("speech.recorder.pyaudio.PyAudio", return_value=fake_audio):
            from speech.recorder import AudioRecorder

            with redirect_stdout(StringIO()):
                recorder = AudioRecorder()
                recorder.start_recording("/tmp/test.wav")
                result = recorder.stop_recording()

            self.assertIsNone(result)
            self.assertTrue(stream.stopped)
            self.assertTrue(stream.closed)
            self.assertIsNone(recorder.stream)
            self.assertIsNone(recorder.recording_thread)

    def test_close_terminates_audio_backend(self):
        stream = FakeStream(read_error=OSError("read stopped"))
        fake_audio = FakePyAudio(stream=stream)
        with patch("speech.recorder.pyaudio.PyAudio", return_value=fake_audio):
            from speech.recorder import AudioRecorder

            with redirect_stdout(StringIO()):
                recorder = AudioRecorder()
                recorder.start_recording("/tmp/test.wav")
                recorder.close()

            self.assertFalse(recorder.is_recording)
            self.assertTrue(stream.closed)
            self.assertTrue(fake_audio.terminated)
            self.assertIsNone(recorder.stream)
            self.assertIsNone(recorder.recording_thread)

    def test_audio_level_uses_pcm_rms_without_numpy(self):
        from speech.recorder import AudioRecorder

        recorder = AudioRecorder.__new__(AudioRecorder)
        samples = array("h", [0, 32767, -32768, 0])
        recorder.frames = [samples.tobytes()]

        level = recorder.get_audio_level()

        self.assertGreater(level, 0.70)
        self.assertLessEqual(level, 1.0)


if __name__ == "__main__":
    unittest.main()
