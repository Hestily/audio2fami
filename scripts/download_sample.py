#!/usr/bin/env python3
"""Download the CC0 Gymnopédie No.1 clip and trim to ~30 seconds."""

from __future__ import annotations

import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEST_DIR = ROOT / "samples"
DEST = DEST_DIR / "gymnopedie_30s.wav"

# Wikimedia Commons: File:Gymnopedie_No._1..ogg — Teknopazzo, CC0
URLS = [
    "https://upload.wikimedia.org/wikipedia/commons/5/54/Gymnopedie_No._1..ogg",
    "https://upload.wikimedia.org/wikipedia/commons/transcoded/5/54/Gymnopedie_No._1..ogg/Gymnopedie_No._1..ogg.ogg",
    "https://commons.wikimedia.org/wiki/Special:FilePath/Gymnopedie_No._1..ogg",
]


def main() -> int:
    DEST_DIR.mkdir(parents=True, exist_ok=True)
    raw = DEST_DIR / "gymnopedie_full.ogg"
    if not DEST.exists():
        last_err = None
        for url in URLS:
            try:
                print(f"downloading {url}", file=sys.stderr)
                req = urllib.request.Request(url, headers={"User-Agent": "audio2fami/1.0"})
                with urllib.request.urlopen(req, timeout=60) as resp, raw.open("wb") as fh:
                    fh.write(resp.read())
                if raw.stat().st_size > 1000:
                    last_err = None
                    break
            except Exception as exc:  # noqa: BLE001
                last_err = exc
        if last_err and not raw.exists():
            print(f"download failed: {last_err}", file=sys.stderr)
            return 1
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-i",
                str(raw),
                "-t",
                "30",
                "-ac",
                "1",
                "-ar",
                "22050",
                str(DEST),
            ],
            check=True,
        )
        print(f"wrote {DEST}", file=sys.stderr)
    else:
        print(f"already have {DEST}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
