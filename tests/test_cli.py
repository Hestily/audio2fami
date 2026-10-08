from pathlib import Path

import pytest

from audio2fami.cli import build_parser, main
from audio2fami.config import ConvertOptions


def test_parser_format_and_mode(tmp_path):
    p = build_parser()
    args = p.parse_args(["song.mp3", "-f", "nsf", "--mode", "lead", "--no-stems"])
    assert args.fmt == "nsf"
    assert args.mode == "lead"
    assert args.stems is False


def test_rejects_unknown_format(tmp_path):
    src = tmp_path / "a.wav"
    src.write_bytes(b"x")
    with pytest.raises(ValueError, match="不支持的输出格式"):
        ConvertOptions(
            input_path=src, output_path=tmp_path / "o.bin", format="midi"
        ).validate()


def test_cli_help_exits_zero():
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0
