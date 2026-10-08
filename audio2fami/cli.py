"""Command-line entry: `audio2fami song.mp3 -f mp3` or `audio2fami ui`."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from audio2fami import __version__
from audio2fami.config import (
    DEFAULT_GRID,
    DEFAULT_TEMPO,
    MODES,
    OUTPUT_FORMATS,
    ConvertOptions,
    default_output_path,
)
from audio2fami.logutil import default_progress
from audio2fami.paths import ENV_FAMISTUDIO, ENV_FFMPEG
from audio2fami.pipeline import PipelineError, convert, convert_from_midi


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="audio2fami",
        description="把任意音频转成 NES 风格 8-bit 音乐（FamiStudio 芯片渲染）。",
    )
    p.add_argument("--version", action="version", version=f"audio2fami {__version__}")
    p.add_argument(
        "input",
        nargs="?",
        help="输入音频（ffmpeg 能读的都可）。子命令 `ui` 启动网页界面。",
    )
    p.add_argument(
        "-f",
        "--format",
        dest="fmt",
        default="wav",
        choices=OUTPUT_FORMATS,
        help="输出格式: wav / mp3 / ogg / nsf / txt / fms（默认 wav）",
    )
    p.add_argument("-o", "--output", type=Path, help="输出路径")
    p.add_argument(
        "--mode",
        default="full",
        choices=MODES,
        help="lead=仅主旋律, harmony=主旋律+和声, full=四声部（默认）",
    )
    stems = p.add_mutually_exclusive_group()
    stems.add_argument(
        "--stems",
        action="store_true",
        help="先用 Demucs 分轨（需 extras: stems）",
    )
    stems.add_argument(
        "--no-stems",
        action="store_true",
        default=True,
        help="不分轨（默认）",
    )
    p.add_argument("--transpose", type=int, default=0, help="移调，半音，-24..24")
    p.add_argument("--tempo", type=int, default=DEFAULT_TEMPO, help="量化 BPM（默认 120）")
    p.add_argument(
        "--grid",
        type=int,
        default=DEFAULT_GRID,
        choices=(4, 8, 16, 32),
        help="量化网格：4=四分 / 8=八分 / 16=十六分 / 32=三十二分",
    )
    p.add_argument("--duration", type=float, default=None, help="只处理前 N 秒")
    p.add_argument(
        "--keep-intermediates",
        action="store_true",
        help="保留分轨、原始 MIDI、清理后 MIDI、FamiStudio 文本工程",
    )
    p.add_argument("--work-dir", type=Path, help="中间文件目录")
    p.add_argument("--from-midi", type=Path, help="跳过转写，直接从 MIDI 进入映射/导出")
    p.add_argument(
        "--famistudio-dir",
        type=Path,
        help=f"FamiStudio 解压目录（也可用环境变量 {ENV_FAMISTUDIO}）",
    )
    p.add_argument(
        "--ffmpeg",
        type=Path,
        help=f"ffmpeg 可执行文件路径（也可用环境变量 {ENV_FFMPEG}）",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "ui":
        from audio2fami.ui import launch

        ui = argparse.ArgumentParser(prog="audio2fami ui", description="启动本地 Web UI")
        ui.add_argument("--host", default="0.0.0.0")
        ui.add_argument("--port", type=int, default=43187)
        args = ui.parse_args(argv[1:])
        launch(host=args.host, port=args.port)
        return 0

    parser = build_parser()
    args = parser.parse_args(argv)

    if args.ffmpeg:
        os.environ[ENV_FFMPEG] = str(Path(args.ffmpeg).resolve())
    if args.famistudio_dir:
        os.environ[ENV_FAMISTUDIO] = str(Path(args.famistudio_dir).resolve())

    if args.from_midi:
        src = Path(args.from_midi)
        dest = Path(args.output) if args.output else default_output_path(src, args.fmt)
        try:
            out = convert_from_midi(
                src,
                dest,
                fmt=args.fmt,
                mode=args.mode,
                tempo=args.tempo,
                grid=args.grid,
                transpose=args.transpose,
                famistudio_dir=args.famistudio_dir,
            )
        except (PipelineError, Exception) as exc:
            default_progress(f"错误: {exc}")
            return 1
        print(out)
        return 0

    if not args.input:
        parser.print_help()
        return 2

    src = Path(args.input)
    dest = Path(args.output) if args.output else default_output_path(src, args.fmt)
    opts = ConvertOptions(
        input_path=src,
        output_path=dest,
        format=args.fmt,
        mode=args.mode,
        stems=bool(args.stems),
        transpose=args.transpose,
        tempo=args.tempo,
        grid=args.grid,
        duration=args.duration,
        keep_intermediates=args.keep_intermediates,
        work_dir=args.work_dir,
        famistudio_dir=args.famistudio_dir,
        ffmpeg_path=args.ffmpeg,
    )
    try:
        out = convert(opts)
    except (PipelineError, FileNotFoundError, ValueError) as exc:
        default_progress(f"错误: {exc}")
        return 1
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
