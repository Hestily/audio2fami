"""Drive official FamiStudio headlessly on Linux and Windows."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from audio2fami.config import FAMISTUDIO_COMMAND, FAMISTUDIO_VERSION
from audio2fami.logutil import StageLog
from audio2fami.paths import (
    ENV_DOTNET_ROOT,
    find_dotnet,
    famistudio_search_dirs,
    is_famistudio_dir,
    is_windows,
)

# Hide an extra console window when launching FamiStudio.exe from the GUI.
_CREATE_NO_WINDOW = 0x08000000


class FamiStudioError(RuntimeError):
    pass


def find_famistudio_dir(explicit: Path | None = None) -> Path:
    for c in famistudio_search_dirs(explicit):
        if is_famistudio_dir(c):
            return c
    raise FamiStudioError(
        "未找到 FamiStudio。"
        + (
            "请运行 setup.cmd，或把 Windows 便携版解压到 third_party\\FamiStudio。"
            if is_windows()
            else f"请运行 ./setup.sh，或把 {FAMISTUDIO_VERSION} Linux 版解压到 third_party/FamiStudio。"
        )
    )


def famistudio_cmd(famistudio_dir: Path | None = None) -> list[str]:
    """argv prefix: FamiStudio.exe on Windows, `dotnet FamiStudio.dll` elsewhere."""
    root = find_famistudio_dir(famistudio_dir)
    exe = root / "FamiStudio.exe"
    dll = root / "FamiStudio.dll"
    if exe.is_file():
        return [str(exe)]
    if dll.is_file():
        dotnet = find_dotnet()
        if not dotnet:
            raise FamiStudioError(
                "未找到 .NET 运行时。请安装 .NET 8.0 Runtime，"
                + (
                    "或重新运行 setup.cmd（会写入 %USERPROFILE%\\.dotnet）。"
                    if is_windows()
                    else "或运行 ./setup.sh（会写入 ~/.dotnet）。"
                )
            )
        return [str(dotnet), str(dll)]
    raise FamiStudioError(f"{root} 里既没有 FamiStudio.exe 也没有 FamiStudio.dll")


def _subprocess_kwargs() -> dict:
    kw: dict = {
        "check": False,
        "capture_output": True,
        "text": True,
        "encoding": "utf-8",
        "errors": "replace",
    }
    if is_windows():
        kw["creationflags"] = _CREATE_NO_WINDOW
    return kw


def run_famistudio(
    args: list[str],
    *,
    famistudio_dir: Path | None = None,
    log: StageLog | None = None,
) -> str:
    root = find_famistudio_dir(famistudio_dir)
    cmd = famistudio_cmd(root) + [str(a) for a in args]
    env = os.environ.copy()
    env.setdefault("DOTNET_SYSTEM_GLOBALIZATION_INVARIANT", "0")
    dotnet = find_dotnet()
    if dotnet:
        env.setdefault(ENV_DOTNET_ROOT, str(dotnet.parent))
    if log:
        log.info(" ".join(cmd))
    try:
        proc = subprocess.run(
            cmd,
            env=env,
            cwd=str(root),
            **_subprocess_kwargs(),
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
    project_txt = project_txt.resolve()
    dest = dest.resolve()
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
