"""Unit tests for quantization, voice reduction, and NES channel mapping."""

from __future__ import annotations

import pretty_midi

from audio2fami.midi_cleanup import (
    SimpleNote,
    collect_notes,
    drop_tiny,
    grid_seconds,
    map_mix,
    midi_to_note_name,
    quantize_drums,
    quantize_to_tracks,
    song_from_pretty_midi,
    write_cleaned_midi,
)


def _n(pitch, start, end, vel=80) -> SimpleNote:
    return SimpleNote(pitch, start, end, vel)


def test_midi_to_note_name_c4():
    assert midi_to_note_name(60) == "C4"
    assert midi_to_note_name(61) == "C#4"
    assert midi_to_note_name(12) == "C0"
    assert midi_to_note_name(107) == "B7"
    assert midi_to_note_name(0) == "C0"  # clamped
    assert midi_to_note_name(200) == "B7"


def test_grid_seconds_matches_famitracker():
    # 16th notes at 120 BPM, BeatLength=4 → 0.125 s
    assert abs(grid_seconds(120, 16) - 0.125) < 1e-9
    # 16th notes at 150 BPM → 0.1 s
    assert abs(grid_seconds(150, 16) - 0.1) < 1e-9


def test_drop_tiny_notes():
    notes = [_n(60, 0.0, 0.01), _n(64, 0.0, 0.4)]
    kept = drop_tiny(notes, 0.04)
    assert [n.pitch for n in kept] == [64]


def test_quantize_keeps_highest_voice():
    # Two overlapping notes: C4 + C5. Melody should keep C5.
    notes = [_n(60, 0.0, 0.5), _n(72, 0.0, 0.5)]
    tracks = quantize_to_tracks(notes, grid=0.125, n_tracks=2, prefer="high")
    assert tracks[0][0].pitch == 72
    assert tracks[1][0].pitch == 60


def test_quantize_is_monophonic_per_track():
    notes = [
        _n(72, 0.00, 0.40),
        _n(74, 0.10, 0.30),  # overlaps, lower than first after ranking...
        _n(67, 0.00, 0.40),
    ]
    tracks = quantize_to_tracks(notes, grid=0.125, n_tracks=1, prefer="high")
    assert len(tracks) == 1
    # No overlapping notes on a single voice
    ordered = sorted(tracks[0], key=lambda n: n.start)
    for a, b in zip(ordered, ordered[1:]):
        assert a.end <= b.start + 1e-6


def test_map_mix_lead_only_uses_pulse1():
    pitched = [_n(72, 0, 0.5), _n(60, 0, 0.5), _n(48, 0, 0.5)]
    song = map_mix(pitched, [], mode="lead", tempo=120, grid_div=16)
    assert song.pulse1 and not song.pulse2 and not song.triangle and not song.noise
    assert song.pulse1[0].pitch == 72


def test_map_mix_harmony_two_pulses():
    pitched = [_n(72, 0, 0.5), _n(67, 0, 0.5)]
    song = map_mix(pitched, [], mode="harmony", tempo=120, grid_div=16)
    assert song.pulse1[0].pitch == 72
    assert song.pulse2[0].pitch == 67
    assert not song.triangle


def test_map_mix_full_routes_bass_and_drums():
    pitched = [_n(72, 0, 0.5), _n(64, 0, 0.5), _n(36, 0, 0.5)]
    drums = [SimpleNote(36, 0.0, 0.1, 100, noise_name="B2")]
    song = map_mix(pitched, drums, mode="full", tempo=120, grid_div=16, bass_cutoff=48)
    assert song.pulse1[0].pitch == 72
    assert song.pulse2[0].pitch == 64
    assert song.triangle[0].pitch == 36
    assert song.noise and song.noise[0].noise_name == "B2"


def test_quantize_drums_one_hit_per_cell():
    drums = [
        SimpleNote(36, 0.00, 0.05, 40, "B2"),
        SimpleNote(38, 0.02, 0.08, 110, "F3"),
    ]
    hits = quantize_drums(drums, 0.125)
    assert len(hits) == 1
    assert hits[0].noise_name == "F3"


def _piano_midi(path):
    pm = pretty_midi.PrettyMIDI(initial_tempo=120)
    piano = pretty_midi.Instrument(program=0, name="piano")
    # C major arpeggio + a low bass C
    for i, pitch in enumerate([60, 64, 67, 72]):
        piano.notes.append(
            pretty_midi.Note(velocity=90, pitch=pitch, start=i * 0.25, end=i * 0.25 + 0.2)
        )
    piano.notes.append(pretty_midi.Note(velocity=80, pitch=36, start=0, end=1.0))
    drums = pretty_midi.Instrument(program=0, is_drum=True, name="drums")
    drums.notes.append(pretty_midi.Note(velocity=100, pitch=36, start=0.0, end=0.1))
    drums.notes.append(pretty_midi.Note(velocity=90, pitch=38, start=0.5, end=0.6))
    pm.instruments.extend([piano, drums])
    pm.write(str(path))
    return path


def test_song_from_pretty_midi_and_roundtrip(tmp_path):
    mid = _piano_midi(tmp_path / "in.mid")
    pm = pretty_midi.PrettyMIDI(str(mid))
    pitched = collect_notes(pm, drums=False)
    drums = collect_notes(pm, drums=True)
    assert len(pitched) == 5
    assert len(drums) == 2

    song = song_from_pretty_midi(pm, mode="full", tempo=120, grid=16)
    assert song.note_count() >= 3
    out = tmp_path / "cleaned.mid"
    write_cleaned_midi(song, out)
    back = pretty_midi.PrettyMIDI(str(out))
    names = [i.name for i in back.instruments]
    # pretty_midi omits empty tracks on write
    assert "Pulse1" in names
    assert "Triangle" in names
    assert "Noise" in names
    assert any(i.notes for i in back.instruments)
