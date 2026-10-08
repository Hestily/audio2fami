"""Write a FamiStudio text project from NES-mapped notes.

FamiStudio's Linux CLI does **not** accept MIDI. The documented (and verified)
workaround is to emit this text format and then run wav/mp3/ogg/nsf-export.
The text file is also the hand-editable project: open it in FamiStudio and
Save As .fms. Binary .fms cannot be written headlessly.
"""

from __future__ import annotations

from pathlib import Path

from audio2fami.config import FAMISTUDIO_VERSION
from audio2fami.midi_cleanup import (
    ChannelSong,
    SimpleNote,
    beat_length_for_grid,
    grid_seconds,
    midi_to_note_name,
)

PATTERN_LENGTH = 64  # rows per pattern (FamiTracker tempo)
SPEED = 6

INSTRUMENTS = {
    "pulse1": "Lead",
    "pulse2": "Harmony",
    "triangle": "Bass",
    "noise": "Drum",
}

CHANNEL_TYPES = {
    "pulse1": "Square1",
    "pulse2": "Square2",
    "triangle": "Triangle",
    "noise": "Noise",
}


def velocity_to_volume(vel: int) -> int:
    return max(1, min(15, round(vel * 15 / 127)))


def note_value(note: SimpleNote, channel: str) -> str:
    if channel == "noise":
        return note.noise_name or midi_to_note_name(note.pitch)
    return midi_to_note_name(note.pitch)


def _quote(value: str) -> str:
    return value.replace('"', '""')


def attr(name: str, value) -> str:
    return f' {name}="{_quote(str(value))}"'


def rows_for(song: ChannelSong) -> tuple[float, int]:
    cell = grid_seconds(song.tempo, song.grid)
    return cell, beat_length_for_grid(song.grid)


def split_into_patterns(
    notes: list[SimpleNote],
    cell: float,
    pattern_len: int,
    n_patterns: int,
) -> list[list[tuple[int, int, SimpleNote]]]:
    """Return per-pattern list of (row, duration_rows, note)."""
    buckets: list[list[tuple[int, int, SimpleNote]]] = [[] for _ in range(n_patterns)]
    for n in notes:
        start_row = int(round(n.start / cell))
        end_row = int(round(n.end / cell))
        if end_row <= start_row:
            end_row = start_row + 1
        row = start_row
        while row < end_row:
            pat = row // pattern_len
            if pat >= n_patterns:
                break
            local = row % pattern_len
            room = pattern_len - local
            dur = min(room, end_row - row)
            buckets[pat].append((local, dur, n))
            row += dur
    return buckets


def render_fami_text(
    song: ChannelSong,
    *,
    name: str = "audio2fami",
    author: str = "audio2fami",
    version: str = FAMISTUDIO_VERSION,
) -> str:
    cell, beat_length = rows_for(song)
    end = song.end_time()
    total_rows = max(1, int(round(end / cell)))
    # leave a little tail so the last note can decay
    total_rows += beat_length
    n_patterns = max(1, (total_rows + PATTERN_LENGTH - 1) // PATTERN_LENGTH)

    lines: list[str] = []
    lines.append(
        f"Project{attr('Version', version)}{attr('TempoMode', 'FamiTracker')}"
        f"{attr('Name', name)}{attr('Author', author)}"
    )
    lines.append(f"\tInstrument{attr('Name', 'Lead')}")
    lines.append(
        '\t\tEnvelope Type="Volume" Length="8" Values="15,14,13,12,11,10,9,8"'
    )
    lines.append('\t\tEnvelope Type="DutyCycle" Length="1" Values="2"')
    lines.append(f"\tInstrument{attr('Name', 'Harmony')}")
    lines.append(
        '\t\tEnvelope Type="Volume" Length="8" Values="12,11,10,9,8,7,6,5"'
    )
    lines.append('\t\tEnvelope Type="DutyCycle" Length="1" Values="1"')
    lines.append(f"\tInstrument{attr('Name', 'Bass')}")
    lines.append('\t\tEnvelope Type="Volume" Length="1" Values="15"')
    lines.append(f"\tInstrument{attr('Name', 'Drum')}")
    lines.append('\t\tEnvelope Type="Volume" Length="4" Values="15,10,5,0"')

    lines.append(
        f"\tSong{attr('Name', 'Song')}{attr('Length', n_patterns)}"
        f"{attr('LoopPoint', -1)}{attr('PatternLength', PATTERN_LENGTH)}"
        f"{attr('BeatLength', beat_length)}"
        f"{attr('FamiTrackerTempo', song.tempo)}"
        f"{attr('FamiTrackerSpeed', SPEED)}"
    )

    for ch in ("pulse1", "pulse2", "triangle", "noise"):
        lines.append(f"\t\tChannel{attr('Type', CHANNEL_TYPES[ch])}")
        inst = INSTRUMENTS[ch]
        buckets = split_into_patterns(
            song.channel(ch), cell, PATTERN_LENGTH, n_patterns
        )
        for i, events in enumerate(buckets):
            if not events:
                continue
            pname = f"{CHANNEL_TYPES[ch]}_{i}"
            lines.append(f"\t\t\tPattern{attr('Name', pname)}")
            # last write wins on a row if two notes land together
            by_row: dict[int, tuple[int, SimpleNote]] = {}
            for row, dur, note in events:
                by_row[row] = (dur, note)
            for row in sorted(by_row):
                dur, note = by_row[row]
                value = note_value(note, ch)
                vol = velocity_to_volume(note.velocity)
                extra = "" if ch == "triangle" else attr("Volume", vol)
                lines.append(
                    f"\t\t\t\tNote{attr('Time', row)}{attr('Value', value)}"
                    f"{attr('Duration', dur)}{attr('Instrument', inst)}{extra}"
                )
            lines.append(
                f"\t\t\tPatternInstance{attr('Time', i)}{attr('Pattern', pname)}"
            )

    lines.append('\t\tChannel Type="DPCM"')
    lines.append("")
    return "\n".join(lines)


def write_fami_text(song: ChannelSong, path: Path, **kwargs) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = render_fami_text(song, **kwargs)
    # Always UTF-8 LF so FamiStudio on Windows does not see CRLF as part of tokens.
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    return path
