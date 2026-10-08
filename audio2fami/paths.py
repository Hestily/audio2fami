"""Locate ffmpeg, FamiStudio, and .NET across Linux and Windows."""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

ENV_FAMISTUDIO = "AUDIO2FAMI_FAMISTUDIO"
ENV_FFMPEG = "AUDIO2FAMI_FFMPEG"
ENV_DOTNET = "AUDIO2FAMI_DOTNET"
ENV_DOTNET_ROOT = "DOTNET_ROOT"


def is_windows() -> bool:
    return os.name == "nt" or sys.platform.startswith("win")


def bundled_ffmpeg_dir() -> Path:
    return REPO_ROOT / "third_party" / "ffmpeg"


def bundled_famistudio_dir() -> Path:
    return REPO_ROOT / "third_party" / "FamiStudio"


def user_famistudio_dir() -> Path:
    if is_windows():
        local = os.environ.get("LOCALAPPDATA")
        base = Path(local) if local else Path.home() / "AppData" / "Local"
        return base / "audio2fami" / "FamiStudio"
    return Path.home() / ".local" / "share" / "audio2fami" / "FamiStudio"


def _is_exe(path: Path) -> bool:
    return path.is_file()


def find_ffmpeg(explicit: str | Path | None = None) -> Path | None:
    """Return ffmpeg executable if found, else None."""
    names = ["ffmpeg.exe", "ffmpeg"] if is_windows() else ["ffmpeg"]
    probe_names = ["ffprobe.exe", "ffprobe"] if is_windows() else ["ffprobe"]

    candidates: list[Path] = []
    if explicit:
        candidates.append(Path(explicit))
    env = os.environ.get(ENV_FFMPEG)
    if env:
        candidates.append(Path(env))

    bundled = bundled_ffmpeg_dir()
    for name in names:
        candidates.append(bundled / name)
        candidates.append(bundled / "bin" / name)

    which = shutil.which("ffmpeg")
    if which:
        candidates.append(Path(which))

    if is_windows():
        pf = os.environ.get("ProgramFiles", r"C:\Program Files")
        candidates.append(Path(pf) / "ffmpeg" / "bin" / "ffmpeg.exe")

    seen: set[Path] = set()
    for c in candidates:
        try:
            c = c.expanduser()
            if c in seen:
                continue
            seen.add(c)
        except OSError:
            continue
        if c.is_dir():
            for name in names:
                hit = c / name
                if _is_exe(hit):
                    return hit
            continue
        if _is_exe(c):
            return c
    return None


def find_ffprobe(ffmpeg: Path | None = None) -> Path | None:
    names = ["ffprobe.exe", "ffprobe"] if is_windows() else ["ffprobe"]
    if ffmpeg is not None:
        sibling = ffmpeg.with_name(names[0] if is_windows() else "ffprobe")
        if _is_exe(sibling):
            return sibling
        # Linux: ffmpeg has no suffix
        sib2 = ffmpeg.parent / ("ffprobe.exe" if is_windows() else "ffprobe")
        if _is_exe(sib2):
            return sib2
    which = shutil.which("ffprobe")
    return Path(which) if which else None


def is_famistudio_dir(path: Path) -> bool:
    return (path / "FamiStudio.exe").is_file() or (path / "FamiStudio.dll").is_file()


def famistudio_search_dirs(explicit: Path | None = None) -> list[Path]:
    dirs: list[Path] = []
    if explicit:
        dirs.append(Path(explicit))
    env = os.environ.get(ENV_FAMISTUDIO)
    if env:
        dirs.append(Path(env))
    dirs.append(bundled_famistudio_dir())
    dirs.append(user_famistudio_dir())
    if not is_windows():
        dirs.append(Path("/opt/famistudio"))
    # Deduplicate while preserving order
    out: list[Path] = []
    seen: set[Path] = set()
    for d in dirs:
        try:
            d = d.expanduser()
        except OSError:
            continue
        if d in seen:
            continue
        seen.add(d)
        out.append(d)
    return out


def find_dotnet() -> Path | None:
    env_override = os.environ.get(ENV_DOTNET)
    candidates: list[Path] = []
    if env_override:
        candidates.append(Path(env_override))
    root = os.environ.get(ENV_DOTNET_ROOT)
    if root:
        candidates.append(Path(root) / ("dotnet.exe" if is_windows() else "dotnet"))
    which = shutil.which("dotnet")
    if which:
        candidates.append(Path(which))
    home = Path.home()
    if is_windows():
        candidates.append(home / ".dotnet" / "dotnet.exe")
        pf = os.environ.get("ProgramFiles", r"C:\Program Files")
        candidates.append(Path(pf) / "dotnet" / "dotnet.exe")
    else:
        candidates.append(home / ".dotnet" / "dotnet")
    for c in candidates:
        if _is_exe(c.expanduser()):
            return c.expanduser()
    return None
