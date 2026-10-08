"""End-to-end: public-domain clip → wav / mp3 / nsf / txt via FamiStudio."""

from __future__ import annotations

import os
from pathlib import Path

import pretty_midi
import pytest

from audio2fami.audio import normalize_input
from audio2fami.config import ConvertOptions
from audio2fami.famistudio import FamiStudioError, find_famistudio_dir
from audio2fami.pipeline import convert, convert_from_midi

SAMPLE = Path(__file__).resolve().parent.parent / "samples" / "gymnopedie_30s.wav"
ARTIFACTS = Path(__file__).resolve().parent.parent / "artifacts"


def _need_famistudio():
    try:
        find_famistudio_dir()
    except FamiStudioError:
        pytest.skip("FamiStudio not installed")


def _fixture_midi(path: Path) -> Path:
    pm = pretty_midi.PrettyMIDI(initial_tempo=108)
    lead = pretty_midi.Instrument(program=0, name="lead")
    # Slow arpeggio reminiscent of the Gymnopédie opening
    phrase = [64, 67, 71, 67, 64, 60, 55, 60]
    t = 0.0
    for pitch in phrase * 3:
        lead.notes.append(
            pretty_midi.Note(velocity=88, pitch=pitch, start=t, end=t + 0.45)
        )
        t += 0.5
    bass = pretty_midi.Instrument(program=32, name="bass")
    for i, pitch in enumerate([36, 43, 41, 36] * 3):
        bass.notes.append(
            pretty_midi.Note(
                velocity=70, pitch=pitch, start=i * 1.0, end=i * 1.0 + 0.9
            )
        )
    pm.instruments.extend([lead, bass])
    path.parent.mkdir(parents=True, exist_ok=True)
    pm.write(str(path))
    return path


@pytest.mark.e2e
def test_from_midi_wav_mp3_nsf_txt(tmp_path):
    _need_famistudio()
    mid = _fixture_midi(tmp_path / "phrase.mid")
    wav = convert_from_midi(mid, tmp_path / "phrase.wav", fmt="wav")
    assert wav.stat().st_size > 2000
    mp3 = convert_from_midi(mid, tmp_path / "phrase.mp3", fmt="mp3")
    assert mp3.stat().st_size > 500
    nsf = convert_from_midi(mid, tmp_path / "phrase.nsf", fmt="nsf")
    assert nsf.stat().st_size > 200
    txt = convert_from_midi(mid, tmp_path / "phrase.txt", fmt="txt")
    text = txt.read_text()
    assert 'TempoMode="FamiTracker"' in text
    assert "Square1" in text


@pytest.mark.e2e
@pytest.mark.skipif(
    os.environ.get("AUDIO2FAMI_SKIP_BASICPITCH") == "1",
    reason="basic-pitch disabled",
)
def test_sample_clip_wav_and_mp3(tmp_path):
    _need_famistudio()
    if not SAMPLE.exists():
        pytest.skip(f"sample missing: {SAMPLE}")

    wav_out = ARTIFACTS / "gymnopedie_nes.wav"
    mp3_out = ARTIFACTS / "gymnopedie_nes.mp3"
    nsf_out = ARTIFACTS / "gymnopedie_nes.nsf"
    txt_out = ARTIFACTS / "gymnopedie_nes.txt"
    ARTIFACTS.mkdir(parents=True, exist_ok=True)

    opts = ConvertOptions(
        input_path=SAMPLE,
        output_path=wav_out,
        format="wav",
        mode="full",
        stems=False,
        tempo=108,
        grid=16,
        duration=25,
        keep_intermediates=True,
        work_dir=tmp_path / "work_wav",
    )
    out = convert(opts)
    assert out.exists() and out.stat().st_size > 8000

    opts.output_path = mp3_out
    opts.format = "mp3"
    opts.work_dir = tmp_path / "work_mp3"
    out_mp3 = convert(opts)
    assert out_mp3.exists() and out_mp3.stat().st_size > 2000

    opts.output_path = nsf_out
    opts.format = "nsf"
    opts.work_dir = tmp_path / "work_nsf"
    out_nsf = convert(opts)
    assert out_nsf.exists() and out_nsf.stat().st_size > 200

    opts.output_path = txt_out
    opts.format = "txt"
    opts.work_dir = tmp_path / "work_txt"
    out_txt = convert(opts)
    assert "Project Version=" in out_txt.read_text()


def test_normalize_rejects_missing(tmp_path):
    with pytest.raises(Exception):
        normalize_input(tmp_path / "nope.wav", tmp_path / "out.wav", duration=1)
