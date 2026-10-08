"""Stage-by-stage progress logging."""

from __future__ import annotations

import sys
from collections.abc import Callable
from datetime import datetime

ProgressFn = Callable[[str], None]


def default_progress(message: str) -> None:
    stamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{stamp}] {message}", file=sys.stderr, flush=True)


class StageLog:
    def __init__(self, total: int, progress: ProgressFn | None = None) -> None:
        self.total = total
        self.index = 0
        self.progress = progress or default_progress

    def step(self, title: str, detail: str = "") -> None:
        self.index += 1
        extra = f" — {detail}" if detail else ""
        self.progress(f"[{self.index}/{self.total}] {title}{extra}")

    def info(self, message: str) -> None:
        self.progress(f"         {message}")

    def warn(self, message: str) -> None:
        self.progress(f"         警告: {message}")
