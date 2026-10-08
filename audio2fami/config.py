"""Shared constants and user-facing option validation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

FAMISTUDIO_VERSION = "4.5.2"
FAMISTUDIO_RELEASE_URL = (
    "https://github.com/BleuBleu/FamiStudio/releases/download/"
    f"{FAMISTUDIO_VERSION}/FamiStudio452-LinuxAMD64.zip"
)

OUTPUT_FORMATS = ("wav", "mp3", "ogg", "nsf", "txt", "fms")
AUDIO_FORMATS = ("wav", "mp3", "ogg")
PROJECT_FORMATS = ("txt", "fms")

Mode = Literal["lead", "harmony", "full"]
MODES: tuple[Mode, ...] = ("lead", "harmony", "full")

MODE_HELP = {
    "lead": "仅主旋律 → 脉冲 1",
    "harmony": "主旋律 + 和声 → 脉冲 1 / 脉冲 2",
    "full": "主旋律 + 和声 + 低音 + 鼓 → 脉冲 1 / 脉冲 2 / 三角波 / 噪声",
}

FAMISTUDIO_COMMAND = {
    "wav": "wav-export",
    "mp3": "mp3-export",
    "ogg": "ogg-export",
    "nsf": "nsf-export",
}

# FamiStudio C0..B7 == MIDI 12..107
MIDI_C0 = 12
MIDI_B7 = 107
DEFAULT_BASS_CUTOFF = 48  # C3 and below → triangle in full-band mix mode
DEFAULT_TEMPO = 120
DEFAULT_GRID = 16
DEFAULT_MIN_NOTE = 0.04  # seconds; tiny notes dropped before grid stitch
NTSC_FPS = 60.0988


@dataclass
class ConvertOptions:
    input_path: Path
    output_path: Path
    format: str
    mode: Mode = "full"
    stems: bool = False
    transpose: int = 0
    tempo: int = DEFAULT_TEMPO
    grid: int = DEFAULT_GRID
    duration: float | None = None
    keep_intermediates: bool = False
    work_dir: Path | None = None
    bass_cutoff: int = DEFAULT_BASS_CUTOFF
    min_note: float = DEFAULT_MIN_NOTE
    sample_rate: int = 44100
    famistudio_dir: Path | None = None

    def validate(self) -> None:
        if self.format not in OUTPUT_FORMATS:
            raise ValueError(
                f"不支持的输出格式 {self.format!r}。"
                f"可选: {', '.join(OUTPUT_FORMATS)}"
            )
        if self.mode not in MODES:
            raise ValueError(
                f"不支持的模式 {self.mode!r}。可选: {', '.join(MODES)}"
            )
        if self.grid not in (4, 8, 16, 32):
            raise ValueError("量化网格 --grid 只能是 4 / 8 / 16 / 32")
        if not 32 <= self.tempo <= 300:
            raise ValueError("tempo 需在 32–300 BPM 之间")
        if not -24 <= self.transpose <= 24:
            raise ValueError("transpose 需在 -24 到 24 个半音之间")
        if self.duration is not None and self.duration <= 0:
            raise ValueError("duration 必须为正数（秒）")
        if not self.input_path.exists():
            raise FileNotFoundError(f"找不到输入文件: {self.input_path}")


def default_output_path(input_path: Path, fmt: str) -> Path:
    ext = "txt" if fmt in PROJECT_FORMATS else fmt
    return input_path.with_name(f"{input_path.stem}_nes.{ext}")


def extension_for(fmt: str) -> str:
    return "txt" if fmt in PROJECT_FORMATS else fmt
