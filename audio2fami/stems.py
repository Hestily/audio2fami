"""Optional Demucs stem separation (maintained fork: adefossez/demucs)."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from audio2fami.logutil import StageLog


class StemError(RuntimeError):
    pass


def demucs_available() -> bool:
    if shutil.which("demucs"):
        return True
    try:
        import demucs  # noqa: F401

        return True
    except ImportError:
        return False


def _demucs_cmd() -> list[str]:
    which = shutil.which("demucs")
    if which:
        return [which]
    return [sys.executable, "-m", "demucs"]


def separate(
    wav: Path,
    dest_dir: Path,
    *,
    model: str = "htdemucs",
    log: StageLog | None = None,
) -> dict[str, Path]:
    if not demucs_available():
        raise StemError(
            "未安装 Demucs。请用 extras 安装：\n"
            "  uv pip install -r requirements-stems.txt\n"
            "或重新运行 ./setup.sh --stems"
        )
    dest_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        *_demucs_cmd(),
        "-n",
        model,
        "-o",
        str(dest_dir),
        "--filename",
        "{stem}.{ext}",
        str(wav),
    ]
    if log:
        log.info(" ".join(cmd))
    try:
        proc = subprocess.run(
            cmd, check=False, capture_output=True, text=True
        )
    except OSError as exc:
        raise StemError(f"无法启动 Demucs: {exc}") from exc
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip()
        raise StemError(f"Demucs 失败: {err or proc.returncode}")

    # demucs writes dest/model/trackname/{drums,bass,other,vocals}.wav
    # --filename {stem}.{ext} still nests under model/
    found: dict[str, Path] = {}
    for path in dest_dir.rglob("*.wav"):
        stem = path.stem.lower()
        if stem in {"vocals", "bass", "drums", "other", "no_vocals"}:
            found[stem] = path
    if not found:
        raise StemError("Demucs 没有产出可识别的分轨 WAV")
    return found


def roles_from_stems(stems: dict[str, Path]) -> dict[str, Path]:
    """Map Demucs names onto pipeline roles."""
    roles: dict[str, Path] = {}
    if "vocals" in stems:
        roles["lead"] = stems["vocals"]
    if "other" in stems:
        roles["harmony"] = stems["other"]
    elif "no_vocals" in stems:
        roles["harmony"] = stems["no_vocals"]
    if "bass" in stems:
        roles["bass"] = stems["bass"]
    if "drums" in stems:
        roles["drums"] = stems["drums"]
    return roles
