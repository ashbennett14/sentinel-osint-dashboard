import importlib.util
from pathlib import Path
import shutil
import tempfile
import unittest
import wave
import struct


WORKER_PATH = Path(__file__).resolve().parents[2] / "scripts" / "generate_audio.py"
SPEC = importlib.util.spec_from_file_location("sentinel_audio_worker", WORKER_PATH)
WORKER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(WORKER)


@unittest.skipUnless(shutil.which("say") and shutil.which("afconvert"), "macOS speech tools required")
class AudioWorkerFallbackTests(unittest.TestCase):
    def test_macos_fallback_renders_ordered_chapters(self):
        sections = [
            {"key": key, "title": key.title(), "text": "Short briefing test."}
            for key in ("opening", "high-north", "eastern-europe", "balkans", "levant", "closing")
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            workdir = Path(temp_dir)
            rendered = WORKER._render_macos(sections, workdir, "Daniel", 175)
            chapters, duration = WORKER._combine_wavs(rendered, workdir / "combined.wav")
            self.assertGreater(duration, 0)
            self.assertEqual([chapter["key"] for chapter in chapters], [s["key"] for s in sections])

    def test_cues_are_distinct_and_match_voice_pcm(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            workdir = Path(temp_dir)
            params = (1, 2, 24000, "NONE")
            payloads = []
            for key in WORKER.AO_KEYS:
                path = workdir / f"{key}.wav"
                WORKER._render_cue(path, key, params)
                with wave.open(str(path), "rb") as cue:
                    self.assertEqual(cue.getnchannels(), 1)
                    self.assertEqual(cue.getsampwidth(), 2)
                    self.assertEqual(cue.getframerate(), 24000)
                    self.assertAlmostEqual(cue.getnframes() / cue.getframerate(), 3.6, places=2)
                    payload = cue.readframes(cue.getnframes())
                    samples = struct.unpack(f"<{len(payload) // 2}h", payload)
                    self.assertLess(max(abs(sample) for sample in samples), 6000)
                    payloads.append(payload)
            self.assertEqual(len(set(payloads)), 4)

    def test_interludes_set_chapter_start_before_speech(self):
        sections = [
            {"key": key, "title": key.title(), "text": "Short briefing test."}
            for key in ("opening", "high-north", "eastern-europe", "balkans", "levant", "closing")
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            workdir = Path(temp_dir)
            spoken = WORKER._render_macos(sections, workdir, "Daniel", 175)
            rendered = WORKER._insert_interludes(spoken, workdir)
            chapters, _ = WORKER._combine_wavs(rendered, workdir / "with-cues.wav")
            starts = {chapter["key"]: chapter["start_seconds"] for chapter in chapters}
            self.assertGreater(starts["eastern-europe"] - starts["high-north"], 3.6)
            self.assertEqual([chapter["key"] for chapter in chapters], [s["key"] for s in sections])


if __name__ == "__main__":
    unittest.main()
