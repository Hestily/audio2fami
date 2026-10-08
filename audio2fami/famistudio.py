"""Drive the official FamiStudio Linux build headlessly."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from audio2fami.config import FAMISTUDIO_COMMAND, FAMISTUDIO_VERSION
from audio2fami.logutil import StageLog

REPO_ROOT = Path(__file__).resolve().parent.parent


class FamiStudioError(RuntimeError):
    pass


def find_dotnet() -> str:
    env = os.environ.get("DOTNET_ROOT")
    candidates = []
    if env:
        candidates.append(Path(env) / "dotnet")
    which = shutil.which("dotnet")
    if which:
        candidates.append(Path(which))
    candidates.append(Path.home() / ".dotnet" / "dotnet")
    for c in candidates:
        if c.is_file() and os.access(c, os.X_OK):
            return str(c)
    raise FamiStudioError(
        "未找到 .NET 运行时。请安装 .NET 8.0 Runtime，"
        "或运行 ./setup.sh（会写入 ~/.dotnet）。"
    )


def find_famistudio_dir(explicit: Path | None = None) -> Path:
    candidates: list[Path] = []
    if explicit:
        candidates.append(explicit)
    env = os.environ.get("AUDIO2FAMI_FAMISTUDIO")
    if env:
        candidates.append(Path(env))
    candidates.extend(
        [
            REPO_ROOT / "third_party" / "FamiStudio",
            Path.home() / ".local" / "share" / "audio2fami" / "FamiStudio",
            Path("/opt/famistudio"),
        ]
    )
    for c in candidates:
        if (c / "FamiStudio.dll").is_file():
            return c
    raise FamiStudioError(
        "未找到 FamiStudio。请运行 ./setup.sh，"
        f"或把 {FAMISTUDIO_VERSION} Linux 版解压到 third_party/FamiStudio。"
    )


def famistudio_cmd(famistudio_dir: Path | None = None) -> list[str]:
    dll = find_famistudio_dir(famistudio_dir) / "FamiStudio.dll"
    return [find_dotnet(), str(dll)]


def run_famistudio(
    args: list[str],
    *,
    famistudio_dir: Path | None = None,
    log: StageLog | None = None,
) -> str:
    cmd = famistudio_cmd(famistudio_dir) + args
    env = os.environ.copy()
    # Headless export does not need a display; keep GLFW from probing wildly.
    env.setdefault("DOTNET_ROOT", str(Path(find_dotnet()).parent))
    if log:
        log.info(" ".join(cmd))
    try:
        proc = subprocess.run(
            cmd,
            check=False,
            capture_output=True,
            text=True,
            env=env,
            cwd=str(find_famistudio_dir(famistudio_dir)),
        )
    except OSError as exc:
        raise FamiStudioError(f"无法启动 FamiStudio: {exc}") from exc
    out = (proc.stdout or "") + (proc.stderr or "")
    if proc.returncode != 0:
        raise FamiStudioError(
            f"FamiStudio 退出码 {proc.returncode}:\n{out.strip() or '(无输出)'}"
        )
    return out


def export(
    project_txt: Path,
    dest: Path,
    fmt: str,
    *,
    duration: float | None = None,
    sample_rate: int = 44100,
    famistudio_dir: Path | None = None,
    log: StageLog | None = None,
) -> Path:
    if fmt not in FAMISTUDIO_COMMAND:
        raise FamiStudioError(f"FamiStudio CLI 不能导出 {fmt}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    command = FAMISTUDIO_COMMAND[fmt]
    extra: list[str] = ["-export-songs:0"]
    if fmt == "wav":
        rate = sample_rate if sample_rate in (11025, 22050, 44100, 48000) else 44100
        extra.append(f"-wav-export-rate:{rate}")
        if duration:
            extra.append(f"-wav-export-duration:{max(1, int(round(duration)))}")
    elif fmt == "mp3":
        extra += ["-mp3-export-rate:44100", "-mp3-export-bitrate:192"]
        if duration:
            extra.append(f"-mp3-export-duration:{max(1, int(round(duration)))}")
    elif fmt == "ogg":
        extra += ["-ogg-export-rate:44100", "-ogg-export-bitrate:192"]
        if duration:
            extra.append(f"-ogg-export-duration:{max(1, int(round(duration)))}")
    elif fmt == "nsf":
        extra.append("-nsf-export-mode:ntsc")

    run_famistudio(
        [str(project_txt), command, str(dest), *extra],
        famistudio_dir=famistudio_dir,
        log=log,
    )
    if not dest.exists() or dest.stat().st_size < 32:
        raise FamiStudioError(f"FamiStudio 没有写出有效文件: {dest}")
    return dest


def help_text(famistudio_dir: Path | None = None) -> str:
    return run_famistudio(["-help"], famistudio_dir=famistudio_dir)
