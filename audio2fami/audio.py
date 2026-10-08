"""ffmpeg helpers: decode anything, trim, encode fallback WAV/MP3."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from audio2fami.logutil import StageLog


class AudioError(RuntimeError):
    pass


def require_ffmpeg() -> str:
    path = shutil.which("ffmpeg")
    if not path:
        raise AudioError(
            "未找到 ffmpeg。请先安装：sudo apt-get install -y ffmpeg"
        )
    return path


def run_ffmpeg(args: list[str], what: str) -> None:
    ffmpeg = require_ffmpeg()
    cmd = [ffmpeg, "-y", "-hide_banner", "-loglevel", "error", *args]
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as exc:
        err = (exc.stderr or exc.stdout or "").strip()
        raise AudioError(f"{what} 失败: {err or exc}") from exc


def normalize_input(
    src: Path,
    dest: Path,
    *,
    duration: float | None,
    sample_rate: int = 22050,
    log: StageLog | None = None,
) -> Path:
    """Decode any ffmpeg-readable file to mono WAV."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    args = ["-i", str(src)]
    if duration:
        args += ["-t", f"{duration:.3f}"]
    args += [
        "-ac",
        "1",
        "-ar",
        str(sample_rate),
        "-c:a",
        "pcm_s16le",
        str(dest),
    ]
    if log:
        log.info(f"ffmpeg 解码 {src.name} → {dest.name}")
    run_ffmpeg(args, "音频解码")
    if not dest.exists() or dest.stat().st_size < 64:
        raise AudioError(f"解码后的 WAV 无效: {dest}")
    return dest


def wav_to_mp3(src: Path, dest: Path, bitrate: str = "192k") -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    run_ffmpeg(
        ["-i", str(src), "-codec:a", "libmp3lame", "-b:a", bitrate, str(dest)],
        "WAV → MP3",
    )
    return dest


def wav_to_ogg(src: Path, dest: Path, bitrate: str = "192k") -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    run_ffmpeg(
        ["-i", str(src), "-codec:a", "libvorbis", "-b:a", bitrate, str(dest)],
        "WAV → OGG",
    )
    return dest


def probe_duration(path: Path) -> float | None:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return None
    try:
        out = subprocess.run(
            [
                ffprobe,
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        return float(out.stdout.strip())
    except (subprocess.CalledProcessError, ValueError):
        return None
