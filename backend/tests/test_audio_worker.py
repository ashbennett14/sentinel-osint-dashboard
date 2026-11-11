import importlib.util
from pathlib import Path
import shutil
import tempfile
import unittest
import wave
import struct
import math


WORKER_PATH = Path(__file__).resolve().parents[2] / "scripts" / "generate_audio.py"
SPEC = importlib.util.spec_from_file_location("sentinel_audio_worker", WORKER_PATH)
WORKER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(WORKER)


@unittest.skipUnless(importlib.util.find_spec("numpy"), "studio mix needs the audio runtime")
class StudioMixTests(unittest.TestCase):
    def test_stereo_cues_and_chapter_boundaries(self):
        score_path = WORKER_PATH.with_name("podcast_score.py")
        spec = importlib.util.spec_from_file_location("sentinel_podcast_score", score_path)
        score = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(score)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            voice = root / "voice.wav"
            rate = 24000
            with wave.open(str(voice), "wb") as stream:
                stream.setparams((1, 2, rate, 0, "NONE", "not compressed"))
                stream.writeframes(b"".join(struct.pack("<h", int(3500 * math.sin(i * .12))) for i in range(rate)))
            keys = ("opening", *WORKER.AO_KEYS, "closing")
            mixed = root / "studio.wav"
            rendered = [({"key": key, "title": key}, voice) for key in keys]
            chapters, duration = score.mix_episode(rendered, mixed)
            self.assertEqual([entry["key"] for entry in chapters], list(keys))
            self.assertEqual(chapters[0]["start_seconds"], 0)
            self.assertGreater(chapters[1]["start_seconds"], 3.25)
            self.assertGreater(duration - chapters[-1]["start_seconds"], 4.65)
            with wave.open(str(mixed), "rb") as stream:
                self.assertEqual(stream.getnchannels(), 2)
                self.assertEqual(stream.getframerate(), rate)
                frames = score.np.frombuffer(stream.readframes(stream.getnframes()), dtype="<i2").reshape(-1, 2)
            self.assertTrue(score.np.any(frames[:, 0] != frames[:, 1]))
            self.assertLess(score.np.abs(frames).max(), 31000)
            self.assertNotEqual(score.cue(1, 2.9, rate).tobytes(), score.cue(2, 2.9, rate).tobytes())


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
