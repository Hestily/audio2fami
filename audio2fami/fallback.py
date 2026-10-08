"""Minimal 2A03-style renderer used only if FamiStudio export fails.

Adapted from the earlier manual-test script (square + triangle + noise).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from audio2fami.audio import wav_to_mp3, wav_to_ogg
from audio2fami.midi_cleanup import ChannelSong

SR = 22050


def _osc(kind: str, freq: float, n: int) -> np.ndarray:
    t = np.arange(n) / SR
    ph = (freq * t) % 1.0
    if kind == "pulse1":
        return np.where(ph < 0.125, 1.0, -1.0) * 0.28
    if kind == "pulse2":
        return np.where(ph < 0.5, 1.0, -1.0) * 0.20
    if kind == "triangle":
        tri = 1 - 4 * np.abs(ph - 0.5)
        return np.round(tri * 7.5) / 7.5 * 0.38
    # noise: short burst, NES-ish
    rng = np.random.default_rng(int(freq * 10) & 0xFFFF)
    return rng.choice([-1.0, 1.0], size=n).astype(np.float64) * 0.16


def _midi_hz(pitch: int) -> float:
    return float(440.0 * (2 ** ((pitch - 69) / 12.0)))


def render_song(song: ChannelSong, dest_wav: Path) -> Path:
    dur = song.end_time() + 0.4
    out = np.zeros(int(dur * SR) + 1, dtype=np.float64)
    specs = (
        ("pulse1", song.pulse1, True),
        ("pulse2", song.pulse2, True),
        ("triangle", song.triangle, False),
        ("noise", song.noise, True),
    )
    for kind, notes, decay in specs:
        for n in notes:
            freq = _midi_hz(n.pitch)
            a = int(n.start * SR)
            b = int(n.end * SR)
            if b <= a:
                b = a + 1
            b = min(b, out.size)
            seg_n = b - a
            if seg_n <= 0:
                continue
            wave = _osc(kind, freq, seg_n)
            env = np.ones(seg_n)
            if decay:
                env = np.maximum(0.25, np.exp(-np.arange(seg_n) / (SR * 0.45)))
            out[a:b] += wave * env * (0.45 + n.velocity / 280)
    peak = float(np.max(np.abs(out))) if out.size else 1.0
    out = out / max(1e-9, peak) * 0.9
    pcm = np.clip(out, -1.0, 1.0)
    dest_wav.parent.mkdir(parents=True, exist_ok=True)
    import wave

    i16 = np.clip(np.round(pcm * 32767), -32768, 32767).astype(np.int16)
    with wave.open(str(dest_wav), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(i16.tobytes())
    return dest_wav


def render_format(song: ChannelSong, dest: Path, fmt: str) -> Path:
    if fmt not in ("wav", "mp3", "ogg"):
        raise RuntimeError(f"回退渲染器不能写出 {fmt}")
    wav = dest.with_suffix(".wav") if fmt != "wav" else dest
    render_song(song, wav)
    if fmt == "mp3":
        return wav_to_mp3(wav, dest)
    if fmt == "ogg":
        return wav_to_ogg(wav, dest)
    return wav
