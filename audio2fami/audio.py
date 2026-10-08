"""ffmpeg helpers: decode anything, trim, encode fallback WAV/MP3."""

from __future__ import annotations

import subprocess
from pathlib import Path

from audio2fami.logutil import StageLog
from audio2fami.paths import ENV_FFMPEG, find_ffmpeg, find_ffprobe, is_windows


class AudioError(RuntimeError):
    pass


def require_ffmpeg(explicit: str | Path | None = None) -> str:
    path = find_ffmpeg(explicit)
    if not path:
        if is_windows():
            raise AudioError(
                "未找到 ffmpeg。请运行 setup.cmd（会下载到 third_party\\ffmpeg），"
                f"或设置环境变量 {ENV_FFMPEG} 指向 ffmpeg.exe。"
            )
        raise AudioError(
            "未找到 ffmpeg。请先安装：sudo apt-get install -y ffmpeg"
            f"，或设置 {ENV_FFMPEG}。"
        )
    return str(path)


def run_ffmpeg(args: list[str], what: str, ffmpeg: str | Path | None = None) -> None:
    exe = require_ffmpeg(ffmpeg)
    cmd = [exe, "-y", "-hide_banner", "-loglevel", "error", *args]
    try:
        subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
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
    ffmpeg: str | Path | None = None,
) -> Path:
    """Decode any ffmpeg-readable file to mono WAV."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    src = src.resolve()
    dest = dest.resolve()
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
    run_ffmpeg(args, "音频解码", ffmpeg=ffmpeg)
    if not dest.exists() or dest.stat().st_size < 64:
        raise AudioError(f"解码后的 WAV 无效: {dest}")
    return dest


def wav_to_mp3(src: Path, dest: Path, bitrate: str = "192k") -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    run_ffmpeg(
        ["-i", str(src.resolve()), "-codec:a", "libmp3lame", "-b:a", bitrate, str(dest.resolve())],
        "WAV → MP3",
    )
    return dest


def wav_to_ogg(src: Path, dest: Path, bitrate: str = "192k") -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    run_ffmpeg(
        ["-i", str(src.resolve()), "-codec:a", "libvorbis", "-b:a", bitrate, str(dest.resolve())],
        "WAV → OGG",
    )
    return dest


def probe_duration(path: Path) -> float | None:
    ffmpeg = find_ffmpeg()
    ffprobe = find_ffprobe(ffmpeg)
    if not ffprobe:
        return None
    try:
        out = subprocess.run(
            [
                str(ffprobe),
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(path.resolve()),
            ],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        return float(out.stdout.strip())
    except (subprocess.CalledProcessError, ValueError):
        return None
