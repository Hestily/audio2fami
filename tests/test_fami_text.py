"""FamiStudio text generator + headless import/export."""

from __future__ import annotations

from pathlib import Path

import pytest

from audio2fami.config import FAMISTUDIO_VERSION
from audio2fami.fami_text import render_fami_text, write_fami_text
from audio2fami.famistudio import FamiStudioError, export, find_famistudio_dir
from audio2fami.midi_cleanup import ChannelSong, SimpleNote


def _toy_song() -> ChannelSong:
    return ChannelSong(
        pulse1=[SimpleNote(72, 0.0, 0.5, 100), SimpleNote(76, 0.5, 1.0, 90)],
        pulse2=[SimpleNote(67, 0.0, 1.0, 70)],
        triangle=[SimpleNote(36, 0.0, 1.0, 80)],
        noise=[SimpleNote(36, 0.0, 0.1, 110, noise_name="B2")],
        tempo=120,
        grid=16,
    )


def test_render_contains_required_objects():
    text = render_fami_text(_toy_song(), name="Unit", author="test")
    assert f'Version="{FAMISTUDIO_VERSION}"' in text
    assert 'TempoMode="FamiTracker"' in text
    assert 'Channel Type="Square1"' in text
    assert 'Channel Type="Square2"' in text
    assert 'Channel Type="Triangle"' in text
    assert 'Channel Type="Noise"' in text
    assert 'Channel Type="DPCM"' in text
    assert 'Value="C5"' in text  # MIDI 72
    assert 'Instrument Name="Lead"' in text
    assert 'LoopPoint="-1"' in text


def test_write_fami_text(tmp_path):
    path = write_fami_text(_toy_song(), tmp_path / "song.txt")
    assert path.exists()
    assert "Project Version=" in path.read_text()


def _famistudio_or_skip():
    try:
        return find_famistudio_dir()
    except FamiStudioError:
        pytest.skip("FamiStudio not installed")


@pytest.mark.e2e
def test_famistudio_imports_generated_text(tmp_path):
    _famistudio_or_skip()
    txt = write_fami_text(_toy_song(), tmp_path / "song.txt", name="Toy")
    wav = tmp_path / "toy.wav"
    export(txt, wav, "wav", sample_rate=22050)
    assert wav.exists() and wav.stat().st_size > 1000
    header = wav.read_bytes()[:4]
    assert header == b"RIFF"
