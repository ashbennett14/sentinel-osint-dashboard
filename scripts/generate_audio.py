#!/usr/bin/env python3
"""Render a chapter manifest to M4A, preferring Kokoro and falling back to macOS."""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import shutil
import struct
import subprocess
import tempfile
import wave
from pathlib import Path


AO_KEYS = ("high-north", "eastern-europe", "balkans", "levant")
CUE_MOTIFS = {
    "opening": (293.66, 440.00, 587.33),
    "high-north": (293.66, 349.23, 440.00),
    "eastern-europe": (261.63, 311.13, 392.00),
    "balkans": (293.66, 392.00, 440.00),
    "levant": (329.63, 392.00, 493.88),
}
CUE_DURATION_SECONDS = 3.6


def _chunks(text: str, limit: int = 420) -> list[str]:
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    chunks: list[str] = []
    current = ""
    for sentence in sentences:
        if current and len(current) + len(sentence) + 1 > limit:
            chunks.append(current)
            current = sentence
        else:
            current = f"{current} {sentence}".strip()
    if current:
        chunks.append(current)
    return chunks or [text]


def _render_neural(sections: list[dict], workdir: Path, voice: str, speed: float) -> list[tuple[dict, Path]]:
    from kokoro_mlx import KokoroTTS

    tts = KokoroTTS.from_pretrained("mlx-community/Kokoro-82M-bf16")
    rendered: list[tuple[dict, Path]] = []
    counter = 0
    for section in sections:
        for chunk in _chunks(section["text"]):
            path = workdir / f"neural-{counter:03d}.wav"
            tts.save(chunk, str(path), voice=voice, speed=speed, sample_rate=24000)
            rendered.append((section, path))
            counter += 1
    return rendered


def _render_onnx(
    sections: list[dict], workdir: Path, voice: str, speed: float, model_path: Path, voices_path: Path
) -> list[tuple[dict, Path]]:
    import soundfile as sf
    from kokoro_onnx import Kokoro

    if not model_path.is_file() or not voices_path.is_file():
        raise FileNotFoundError("Kokoro ONNX model assets are unavailable")
    tts = Kokoro(str(model_path), str(voices_path))
    rendered = []
    counter = 0
    for section in sections:
        for chunk in _chunks(section["text"]):
            path = workdir / f"onnx-{counter:03d}.wav"
            samples, sample_rate = tts.create(chunk, voice=voice, speed=speed, lang="en-gb")
            sf.write(path, samples, sample_rate, subtype="PCM_16")
            rendered.append((section, path))
            counter += 1
    return rendered


def _render_macos(
    sections: list[dict],
    workdir: Path,
    voice: str,
    rate: int,
) -> list[tuple[dict, Path]]:
    rendered: list[tuple[dict, Path]] = []
    for index, section in enumerate(sections):
        aiff = workdir / f"macos-{index:03d}.aiff"
        wav = workdir / f"macos-{index:03d}.wav"
        subprocess.run(
            ["/usr/bin/say", "-v", voice, "-r", str(rate), "-o", str(aiff), section["text"]],
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            ["/usr/bin/afconvert", "-f", "WAVE", "-d", "LEI16", str(aiff), str(wav)],
            check=True,
            capture_output=True,
            text=True,
        )
        rendered.append((section, wav))
    return rendered


def _render_cue(path: Path, key: str, audio_params: tuple) -> None:
    """Create a quiet, original broadcast sting matching the rendered voice PCM."""
    channels, sample_width, sample_rate, compression = audio_params
    if sample_width != 2 or compression != "NONE":
        raise ValueError("Musical cues require uncompressed 16-bit PCM voice audio")
    motif = CUE_MOTIFS[key]
    frame_count = int(CUE_DURATION_SECONDS * sample_rate)
    frames = bytearray()
    # SEN / TI / NEL: a short-short-long signature, with a soft fifth underneath.
    # Regional variants share the rhythm and sound palette of the opening ident.
    note_starts = (0.20, 0.62, 1.12)
    for frame in range(frame_count):
        t = frame / sample_rate
        fade_in = min(1.0, t / 0.18)
        fade_out = min(1.0, max(0.0, CUE_DURATION_SECONDS - t) / 0.55)
        master = fade_in * fade_out
        pad_envelope = math.sin(math.pi * t / CUE_DURATION_SECONDS) ** 2
        root = motif[0] / 2
        sample = pad_envelope * (
            0.018 * math.sin(2 * math.pi * root * t)
            + 0.012 * math.sin(2 * math.pi * root * 1.5 * t)
            + 0.008 * math.sin(2 * math.pi * root * 2 * t)
        )
        for index, (frequency, start) in enumerate(zip(motif, note_starts)):
            age = t - start
            # Rounded mallet attack, gently decaying harmonics and two quiet
            # echoes provide depth without harsh beeps, percussion or sirens.
            duration = 2.3 if index == 2 else 1.3
            for delay, gain in ((0.0, 1.0), (0.19, 0.20), (0.38, 0.09)):
                echo_age = age - delay
                if 0 <= echo_age <= duration:
                    envelope = min(1.0, echo_age / 0.025) * math.exp(-2.6 * echo_age)
                    envelope *= min(1.0, (duration - echo_age) / 0.12)
                    sample += gain * envelope * (
                        0.095 * math.sin(2 * math.pi * frequency * echo_age)
                        + 0.022 * math.exp(-3 * echo_age) * math.sin(2 * math.pi * frequency * 2 * echo_age)
                        + 0.009 * math.exp(-5 * echo_age) * math.sin(2 * math.pi * frequency * 3 * echo_age)
                    )
        value = max(-1.0, min(1.0, sample * master))
        packed = struct.pack("<h", int(value * 32767))
        frames.extend(packed * channels)
    with wave.open(str(path), "wb") as destination:
        destination.setnchannels(channels)
        destination.setsampwidth(sample_width)
        destination.setframerate(sample_rate)
        destination.setcomptype("NONE", "not compressed")
        destination.writeframes(frames)


def _insert_interludes(rendered: list[tuple[dict, Path]], workdir: Path) -> list[tuple[dict, Path]]:
    """Insert one AO-specific cue before the first spoken chunk of every AO."""
    if not rendered:
        return rendered
    with wave.open(str(rendered[0][1]), "rb") as source:
        audio_params = (
            source.getnchannels(), source.getsampwidth(), source.getframerate(), source.getcomptype()
        )
    result = []
    inserted = set()
    for section, path in rendered:
        key = section["key"]
        if key in ("opening", *AO_KEYS) and key not in inserted:
            cue_path = workdir / f"cue-{key}.wav"
            _render_cue(cue_path, key, audio_params)
            result.append((section, cue_path))
            inserted.add(key)
        result.append((section, path))
    if not set(AO_KEYS).issubset(inserted):
        raise ValueError("One or more AO musical cues could not be inserted")
    return result


def _combine_wavs(rendered: list[tuple[dict, Path]], output: Path) -> tuple[list[dict], float]:
    if not rendered:
        raise ValueError("No audio segments were rendered")
    chapters: list[dict] = []
    elapsed = 0.0
    params = None
    with wave.open(str(output), "wb") as destination:
        current_key = None
        for section, path in rendered:
            with wave.open(str(path), "rb") as source:
                source_params = (
                    source.getnchannels(),
                    source.getsampwidth(),
                    source.getframerate(),
                    source.getcomptype(),
                )
                if params is None:
                    params = source_params
                    destination.setnchannels(source_params[0])
                    destination.setsampwidth(source_params[1])
                    destination.setframerate(source_params[2])
                    destination.setcomptype(source_params[3], "not compressed")
                elif source_params != params:
                    raise ValueError("Rendered audio segments do not share a common PCM format")
                if section["key"] != current_key:
                    chapters.append({
                        "key": section["key"],
                        "title": section["title"],
                        "start_seconds": round(elapsed, 2),
                    })
                    current_key = section["key"]
                frames = source.readframes(source.getnframes())
                destination.writeframes(frames)
                elapsed += source.getnframes() / source.getframerate()
    return chapters, elapsed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--metadata", required=True)
    parser.add_argument("--voice", default="bm_george")
    parser.add_argument("--fallback-voice", default="Daniel")
    parser.add_argument("--speed", type=float, default=1.08)
    parser.add_argument("--fallback-rate", type=int, default=175)
    parser.add_argument("--onnx-model", default=os.getenv("KOKORO_MODEL_PATH", ""))
    parser.add_argument("--onnx-voices", default=os.getenv("KOKORO_VOICES_PATH", ""))
    args = parser.parse_args()

    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    sections = manifest.get("sections") or []
    if [section.get("key") for section in sections] != [
        "opening", "high-north", "eastern-europe", "balkans", "levant", "closing"
    ]:
        raise ValueError("Invalid or incomplete audio manifest")

    output = Path(args.output)
    metadata = Path(args.metadata)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="render-", dir=output.parent) as temp_dir:
        workdir = Path(temp_dir)
        engine = "kokoro-mlx"
        try:
            rendered = _render_neural(sections, workdir, args.voice, args.speed)
        except Exception as neural_error:  # noqa: BLE001
            try:
                engine = "kokoro-onnx"
                rendered = _render_onnx(
                    sections, workdir, args.voice, args.speed,
                    Path(args.onnx_model), Path(args.onnx_voices),
                )
            except Exception as onnx_error:  # noqa: BLE001
                if not Path("/usr/bin/say").is_file():
                    raise RuntimeError(
                        f"Kokoro MLX failed ({neural_error}); Kokoro ONNX failed ({onnx_error})"
                    ) from onnx_error
                engine = f"macOS {args.fallback_voice} fallback"
                rendered = _render_macos(sections, workdir, args.fallback_voice, args.fallback_rate)

        combined = workdir / "combined.wav"
        try:
            from podcast_score import mix_episode
        except ModuleNotFoundError as exc:
            if exc.name != "numpy":
                raise
            # Keep the optional bare macOS system-speech setup usable.
            rendered = _insert_interludes(rendered, workdir)
            chapters, duration = _combine_wavs(rendered, combined)
        else:
            chapters, duration = mix_episode(rendered, combined)
        converter = [
            "/usr/bin/afconvert", str(combined), "-o", str(output), "-f", "m4af", "-d", "aac", "-b", "128000"
        ] if Path("/usr/bin/afconvert").is_file() else [
            shutil.which("ffmpeg") or "ffmpeg", "-y", "-i", str(combined),
            "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(output),
        ]
        subprocess.run(
            converter,
            check=True,
            capture_output=True,
            text=True,
        )
        metadata.write_text(json.dumps({
            "engine": engine,
            "duration_seconds": round(duration, 2),
            "chapters": chapters,
        }), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
