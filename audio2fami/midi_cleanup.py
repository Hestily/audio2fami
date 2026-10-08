"""Quantize MIDI, drop tiny notes, and map voices onto NES channels."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Literal

import pretty_midi

from audio2fami.config import DEFAULT_BASS_CUTOFF, MIDI_B7, MIDI_C0

Prefer = Literal["high", "low"]

PULSE1 = "pulse1"
PULSE2 = "pulse2"
TRIANGLE = "triangle"
NOISE = "noise"
NES_CHANNELS = (PULSE1, PULSE2, TRIANGLE, NOISE)

# General MIDI percussion → FamiStudio noise "pitch" (period flavour)
_DRUM_NOISE = {
    35: "B2",
    36: "B2",  # kick
    37: "D4",
    38: "F3",
    40: "F3",  # snare
    39: "G4",
    41: "A2",
    43: "A2",
    45: "G2",
    47: "G2",  # toms
    42: "C5",
    44: "C5",
    46: "D5",  # hats
    49: "E4",
    51: "E4",
    52: "E4",
    55: "E4",
    57: "E4",  # cymbals
}

NOTE_NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")


@dataclass
class SimpleNote:
    pitch: int
    start: float
    end: float
    velocity: int = 80
    noise_name: str | None = None

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)

    def transposed(self, semitones: int) -> "SimpleNote":
        if self.noise_name is not None:
            return SimpleNote(
                self.pitch, self.start, self.end, self.velocity, self.noise_name
            )
        return SimpleNote(
            clamp_pitch(self.pitch + semitones),
            self.start,
            self.end,
            self.velocity,
            None,
        )


@dataclass
class ChannelSong:
    """One monophonic line per NES channel."""

    pulse1: list[SimpleNote] = field(default_factory=list)
    pulse2: list[SimpleNote] = field(default_factory=list)
    triangle: list[SimpleNote] = field(default_factory=list)
    noise: list[SimpleNote] = field(default_factory=list)
    tempo: int = 120
    grid: int = 16

    def channel(self, name: str) -> list[SimpleNote]:
        return getattr(self, name)

    def all_notes(self) -> Iterable[SimpleNote]:
        for name in NES_CHANNELS:
            yield from self.channel(name)

    def end_time(self) -> float:
        ends = [n.end for n in self.all_notes()]
        return max(ends) if ends else 0.0

    def note_count(self) -> int:
        return sum(1 for _ in self.all_notes())


def clamp_pitch(pitch: int) -> int:
    return max(MIDI_C0, min(MIDI_B7, int(pitch)))


def midi_to_note_name(pitch: int) -> str:
    pitch = clamp_pitch(pitch)
    return f"{NOTE_NAMES[pitch % 12]}{(pitch // 12) - 1}"


def grid_seconds(tempo: int, grid: int) -> float:
    """Length of one quantization cell.

    BeatLength (rows per quarter) = grid / 4, FamiTracker speed = 6,
    so cell = 60 / (tempo * beat_length).
    """
    beat_length = max(1, grid // 4)
    return 60.0 / (tempo * beat_length)


def beat_length_for_grid(grid: int) -> int:
    return max(1, grid // 4)


def collect_notes(
    pm: pretty_midi.PrettyMIDI, *, drums: bool = False
) -> list[SimpleNote]:
    notes: list[SimpleNote] = []
    for inst in pm.instruments:
        is_drum = bool(getattr(inst, "is_drum", False))
        if drums != is_drum:
            continue
        for n in inst.notes:
            if n.end <= n.start:
                continue
            noise = _DRUM_NOISE.get(n.pitch, "D4") if drums else None
            notes.append(
                SimpleNote(
                    pitch=int(n.pitch),
                    start=float(n.start),
                    end=float(n.end),
                    velocity=int(max(1, min(127, n.velocity))),
                    noise_name=noise,
                )
            )
    return notes


def drop_tiny(notes: list[SimpleNote], min_dur: float) -> list[SimpleNote]:
    return [n for n in notes if n.duration >= min_dur]


def transpose_notes(notes: list[SimpleNote], semitones: int) -> list[SimpleNote]:
    if not semitones:
        return list(notes)
    return [n.transposed(semitones) for n in notes]


def quantize_to_tracks(
    notes: list[SimpleNote],
    grid: float,
    n_tracks: int,
    prefer: Prefer = "high",
) -> list[list[SimpleNote]]:
    """Snap notes to a grid and keep the N loudest-register pitches per cell."""
    if n_tracks <= 0 or not notes:
        return [[] for _ in range(max(0, n_tracks))]

    end = max(n.end for n in notes)
    n_cells = max(1, int(round(end / grid)))
    cells: list[list[tuple[int, int]]] = [[] for _ in range(n_cells)]
    for n in notes:
        a = int(round(n.start / grid))
        b = int(round(n.end / grid))
        if b <= a:
            b = a + 1
        for c in range(max(0, a), min(b, n_cells)):
            cells[c].append((n.pitch, n.velocity))

    chosen: list[list[tuple[int, int]]] = []
    reverse = prefer == "high"
    for hits in cells:
        best: dict[int, int] = {}
        for pitch, vel in hits:
            best[pitch] = max(vel, best.get(pitch, 0))
        ranked = sorted(best.items(), key=lambda kv: kv[0], reverse=reverse)
        chosen.append(ranked[:n_tracks])

    tracks: list[list[SimpleNote]] = [[] for _ in range(n_tracks)]
    for voice in range(n_tracks):
        cur_cell: int | None = None
        cur_pitch = 0
        cur_vel = 80
        for c, picks in enumerate(chosen):
            if len(picks) > voice:
                pitch, vel = picks[voice]
                if cur_cell is not None and cur_pitch == pitch:
                    continue
                if cur_cell is not None:
                    tracks[voice].append(
                        SimpleNote(cur_pitch, cur_cell * grid, c * grid, cur_vel)
                    )
                cur_cell, cur_pitch, cur_vel = c, pitch, vel
            elif cur_cell is not None:
                tracks[voice].append(
                    SimpleNote(cur_pitch, cur_cell * grid, c * grid, cur_vel)
                )
                cur_cell = None
        if cur_cell is not None:
            tracks[voice].append(
                SimpleNote(cur_pitch, cur_cell * grid, n_cells * grid, cur_vel)
            )
    return tracks


def quantize_drums(notes: list[SimpleNote], grid: float) -> list[SimpleNote]:
    """One noise hit per cell; newest / highest-velocity wins."""
    if not notes:
        return []
    end = max(n.end for n in notes)
    n_cells = max(1, int(round(end / grid)))
    winners: list[SimpleNote | None] = [None] * n_cells
    for n in notes:
        c = int(round(n.start / grid))
        if c < 0 or c >= n_cells:
            continue
        prev = winners[c]
        if prev is None or n.velocity > prev.velocity:
            hit_end = min((c + 1) * grid, n.end)
            if hit_end <= c * grid:
                hit_end = (c + 1) * grid
            winners[c] = SimpleNote(
                n.pitch,
                c * grid,
                hit_end,
                n.velocity,
                n.noise_name or _DRUM_NOISE.get(n.pitch, "D4"),
            )
    return [n for n in winners if n is not None]


def _empty_song(tempo: int, grid: int) -> ChannelSong:
    return ChannelSong(tempo=tempo, grid=grid)


def map_mix(
    pitched: list[SimpleNote],
    drums: list[SimpleNote],
    *,
    mode: str,
    tempo: int,
    grid_div: int,
    bass_cutoff: int = DEFAULT_BASS_CUTOFF,
    min_note: float = 0.04,
) -> ChannelSong:
    """Map a single mixed transcription onto NES channels."""
    song = _empty_song(tempo, grid_div)
    grid = grid_seconds(tempo, grid_div)
    pitched = drop_tiny(pitched, min_note)

    if mode == "lead":
        tracks = quantize_to_tracks(pitched, grid, 1, "high")
        song.pulse1 = tracks[0]
        return song

    if mode == "harmony":
        tracks = quantize_to_tracks(pitched, grid, 2, "high")
        song.pulse1, song.pulse2 = tracks[0], tracks[1]
        return song

    bass = [n for n in pitched if n.pitch <= bass_cutoff]
    rest = [n for n in pitched if n.pitch > bass_cutoff]
    if not rest and bass:
        # Piano-only pieces: keep the top of the texture as lead.
        rest = [n for n in bass if n.pitch > bass_cutoff - 12] or bass
        bass = [n for n in bass if n not in rest]

    pulse = quantize_to_tracks(rest, grid, 2, "high")
    tri = quantize_to_tracks(bass, grid, 1, "low")
    song.pulse1 = pulse[0]
    song.pulse2 = pulse[1]
    song.triangle = tri[0]
    song.noise = quantize_drums(drums, grid)
    return song


def map_roles(
    role_notes: dict[str, list[SimpleNote]],
    *,
    mode: str,
    tempo: int,
    grid_div: int,
    bass_cutoff: int = DEFAULT_BASS_CUTOFF,
    min_note: float = 0.04,
) -> ChannelSong:
    """Map already-separated stems (lead/harmony/bass/drums/mix)."""
    if "mix" in role_notes and len(role_notes) == 1:
        return map_mix(
            [n for n in role_notes["mix"] if n.noise_name is None],
            [n for n in role_notes["mix"] if n.noise_name is not None],
            mode=mode,
            tempo=tempo,
            grid_div=grid_div,
            bass_cutoff=bass_cutoff,
            min_note=min_note,
        )

    song = _empty_song(tempo, grid_div)
    grid = grid_seconds(tempo, grid_div)

    def take(role: str, prefer: Prefer, n: int = 1) -> list[SimpleNote]:
        notes = drop_tiny(role_notes.get(role, []), min_note)
        if not notes:
            return []
        return quantize_to_tracks(notes, grid, n, prefer)[0] if n == 1 else []

    lead = drop_tiny(role_notes.get("lead", []), min_note)
    harmony = drop_tiny(role_notes.get("harmony", []), min_note)
    bass = drop_tiny(role_notes.get("bass", []), min_note)
    drums = role_notes.get("drums", [])
    leftover = drop_tiny(role_notes.get("mix", []), min_note)

    if not lead and leftover:
        lead = leftover

    if mode == "lead":
        song.pulse1 = quantize_to_tracks(lead or leftover, grid, 1, "high")[0]
        return song

    if mode == "harmony":
        if lead:
            song.pulse1 = quantize_to_tracks(lead, grid, 1, "high")[0]
            src = harmony or leftover
            song.pulse2 = quantize_to_tracks(src, grid, 1, "high")[0] if src else []
        else:
            tracks = quantize_to_tracks(harmony or leftover, grid, 2, "high")
            song.pulse1, song.pulse2 = tracks[0], tracks[1]
        return song

    if lead:
        song.pulse1 = quantize_to_tracks(lead, grid, 1, "high")[0]
    if harmony:
        song.pulse2 = quantize_to_tracks(harmony, grid, 1, "high")[0]
    elif leftover and not lead:
        tracks = quantize_to_tracks(leftover, grid, 2, "high")
        song.pulse1, song.pulse2 = tracks[0], tracks[1]
    elif leftover:
        song.pulse2 = quantize_to_tracks(leftover, grid, 1, "high")[0]

    if not song.pulse1 and leftover:
        song.pulse1 = quantize_to_tracks(leftover, grid, 1, "high")[0]

    if bass:
        song.triangle = quantize_to_tracks(bass, grid, 1, "low")[0]
    elif leftover:
        low = [n for n in leftover if n.pitch <= bass_cutoff]
        song.triangle = quantize_to_tracks(low, grid, 1, "low")[0] if low else []

    song.noise = quantize_drums(drums, grid)
    return song


def song_from_pretty_midi(
    pm: pretty_midi.PrettyMIDI,
    *,
    mode: str = "full",
    tempo: int = 120,
    grid: int = 16,
    transpose: int = 0,
    bass_cutoff: int = DEFAULT_BASS_CUTOFF,
    min_note: float = 0.04,
) -> ChannelSong:
    pitched = transpose_notes(collect_notes(pm, drums=False), transpose)
    drums = collect_notes(pm, drums=True)
    return map_mix(
        pitched,
        drums,
        mode=mode,
        tempo=tempo,
        grid_div=grid,
        bass_cutoff=bass_cutoff,
        min_note=min_note,
    )


def write_cleaned_midi(song: ChannelSong, path) -> None:
    """Write a 4-track MIDI that mirrors NES channel assignment."""
    pm = pretty_midi.PrettyMIDI(initial_tempo=float(song.tempo))
    specs = (
        (song.pulse1, 80, False, "Pulse1"),
        (song.pulse2, 81, False, "Pulse2"),
        (song.triangle, 33, False, "Triangle"),
        (song.noise, 118, True, "Noise"),
    )
    for notes, program, is_drum, name in specs:
        inst = pretty_midi.Instrument(program=program, is_drum=is_drum, name=name)
        for n in notes:
            inst.notes.append(
                pretty_midi.Note(
                    velocity=n.velocity,
                    pitch=clamp_pitch(n.pitch),
                    start=n.start,
                    end=max(n.end, n.start + 1e-3),
                )
            )
        pm.instruments.append(inst)
    pm.write(str(path))
