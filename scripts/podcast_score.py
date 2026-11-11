"""Original stereo score and voice mix for the SENTINEL morning podcast."""

import wave
from itertools import groupby

import numpy as np

TAU = 2 * np.pi
VOICINGS = (
    (38, 53, 57, 60, 64),  # D minor ninth
    (34, 53, 57, 62, 65),  # B-flat major seventh
    (43, 53, 58, 62, 69),  # G minor ninth
    (45, 55, 57, 62, 64),  # A suspended seventh
)
SIGNATURE = (62, 69, 72, 76)


def hz(midi):
    return 440 * 2 ** ((midi - 69) / 12)


def envelope(t, attack, release, duration):
    return np.minimum(1, t / attack) * np.clip((duration - t) / release, 0, 1)


def note(kind, midi, length, rate):
    t = np.arange(round(length * rate)) / rate
    f = hz(midi)
    phase = TAU * f * t
    if kind == "keys":
        return envelope(t, .021, .18, length) * (
            np.exp(-1.9*t) * np.sin(phase + 0.55*np.exp(-5*t)*np.sin(phase*2.002))
            + .23*np.exp(-3.2*t)*np.sin(phase*2) + .08*np.exp(-7*t)*np.sin(phase*4.002)
        )
    if kind == "pad":
        return envelope(t, .65, .8, length)**1.4 * (
            .55*np.sin(phase) + .32*np.sin(phase*.998 + .3) + .12*np.sin(phase*2.002)
        )
    if kind == "bass":
        return envelope(t, .048, .22, length) * (.78*np.sin(phase) + .2*np.sin(phase*2))
    return envelope(t, .006, .075, length) * np.exp(-15*t) * (
        .7*np.sin(phase*np.exp(-1.9*t)) + .16*np.sin(phase*2.19)
    )


def cue(index, seconds, rate):
    mix = np.zeros((round(seconds * rate), 2))

    def put(sound, at, gain, pan=0):
        offset = round(at*rate)
        span = min(len(sound), len(mix)-offset)
        if span > 0:
            gains = np.array([np.sqrt((1-pan)/2), np.sqrt((1+pan)/2)])
            mix[offset:offset+span] += sound[:span, None] * gains * gain

    # A shared four-note identity, voiced differently for each region.
    opening, closing = index == 0, index == 5
    chords = ([0, 1, 2, 3] if opening else [3, 0] if closing else
              [(index-1) % 4, index % 4])
    step = 2.0 if opening else 1.45 if closing else 1.05
    for turn, chord_id in enumerate(chords):
        root, *chord = VOICINGS[chord_id]
        start = turn * step
        put(note("bass", root, step + .15, rate), start+.06, .105 if opening else .075)
        for n, pitch in enumerate(chord):
            put(note("pad", pitch, step+1.05, rate), start+.07*n, .034, (-1)**n*.49)
        for tick, pitch in enumerate(chord[1:]):
            at = start + .10 + tick*(step/4)
            put(note("keys", pitch+12, .8, rate), at, .020, (-1)**tick*.63)
        put(note("pulse", root+12, .30, rate), start+.16, .042)
    if opening or closing:
        motif = SIGNATURE if opening else (76, 72, 69, 62)
        times = (.35, .88, 1.33, 2.02) if opening else (.16, .52, .88, 1.5)
    else:
        offsets = (0, -2, 3, 5)
        motif = tuple(n+offsets[index-1] for n in SIGNATURE)
        times = (.12, .47, .74, 1.24)
    for tick, (at, pitch) in enumerate(zip(times, motif)):
        tone = note("keys", pitch, 1.55 if tick == 3 else 1.1, rate)
        put(tone, at, .15 if opening else .123, (-1)**tick*.17)
        put(tone, at+.13, .022, -.7)
        put(tone, at+.21, .016, .71)
        if tick == 3:
            put(note("keys", pitch-12, 1.5, rate), at+.01, .056)

    # Small stereo room and gentle master fades; keep the centre for speech.
    room = mix.copy()
    for delay, gain in ((.033, .12), (.061, .09), (.107, .055)):
        n = round(delay*rate)
        mix[n:] += room[:-n, ::-1] * gain
    t = np.arange(len(mix)) / rate
    mix *= envelope(t, .075, .65 if opening or closing else .35, seconds)[:, None]
    return mix


def trim_speech(voice, rate):
    active = np.flatnonzero(np.abs(voice) > .006)
    if len(active):
        voice = voice[max(0, active[0]-round(.045*rate)):active[-1]+round(.11*rate)]
    if len(voice) < 2:
        raise ValueError("No speech rendered")
    rms = np.sqrt(np.mean(voice**2))
    gain = min(.105/max(rms, .001), .88/max(np.max(np.abs(voice)), .001))
    return voice*gain


def _read_voice(path):
    with wave.open(str(path), "rb") as stream:
        if stream.getsampwidth() != 2 or stream.getcomptype() != "NONE":
            raise ValueError("Studio mix requires uncompressed 16-bit PCM")
        rate = stream.getframerate()
        samples = np.frombuffer(stream.readframes(stream.getnframes()), dtype="<i2").astype(float)
        return samples.reshape(-1, stream.getnchannels()).mean(axis=1) / 32768, rate


def mix_episode(rendered, output):
    """Mix each chapter in order; offsets start at the music, not the speech."""
    if not rendered:
        raise ValueError("No speech chunks to mix")
    chapters, cursor, rate = [], 0, None
    with wave.open(str(output), "wb") as destination:
        destination.setnchannels(2)
        destination.setsampwidth(2)
        for index, (_, items) in enumerate(groupby(rendered, key=lambda item: item[0]["key"])):
            parts = []
            for section, path in items:
                voice, segment_rate = _read_voice(path)
                if rate is None:
                    rate = segment_rate
                    destination.setframerate(rate)
                if rate != segment_rate:
                    raise ValueError("Voice chunks must use the same sample rate")
                parts.extend((trim_speech(voice, rate), np.zeros(round(.16 * rate))))
            chapters.append({"key": section["key"], "title": section["title"], "start_seconds": round(cursor / rate, 2)})
            voice = np.concatenate(parts)
            if section["key"] == "closing":
                music = cue(index, 4.65, rate)
                mixed = np.zeros((len(voice) + len(music), 2))
                mixed[:len(voice)] = voice[:, None]
                mixed[len(voice):] = music
            else:
                opening = section["key"] == "opening"
                lead = 3.25 if opening else 1.65
                music = cue(index, 8.25 if opening else 2.90, rate)
                onset = round(lead * rate)
                t = np.arange(len(music)) / rate
                duck = 1 - .76 * np.clip((t - lead + .22) / .30, 0, 1)
                mixed = np.zeros((max(len(music), onset + len(voice)), 2))
                mixed[:len(music)] += music * duck[:, None]
                mixed[onset:onset+len(voice)] += voice[:, None]
            peak = float(np.max(np.abs(mixed)))
            if peak > .92:
                mixed *= .92 / peak
            destination.writeframes(np.round(mixed * 32767).astype("<i2").tobytes())
            cursor += len(mixed)
    return chapters, cursor / rate
