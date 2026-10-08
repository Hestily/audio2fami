"""Minimal Gradio UI: upload audio, pick format/mode, convert, play/download."""

from __future__ import annotations

import tempfile
from pathlib import Path

from audio2fami.config import MODES, MODE_HELP, OUTPUT_FORMATS, ConvertOptions
from audio2fami.pipeline import PipelineError, convert


def _convert(
    audio_path,
    fmt: str,
    mode: str,
    stems: bool,
    transpose: int,
    tempo: int,
    grid: int,
    duration,
    progress=None,
):
    logs: list[str] = []

    def on_log(msg: str) -> None:
        logs.append(msg)
        if progress is not None:
            # Gradio 4: progress(progress, desc=...)
            try:
                progress(len(logs) / 12.0, desc=msg)
            except TypeError:
                pass

    if not audio_path:
        return None, None, "请先上传一段音频。"

    src = Path(audio_path)
    suffix = ".txt" if fmt in ("txt", "fms") else f".{fmt}"
    dest = Path(tempfile.mkdtemp(prefix="audio2fami-ui-")) / f"{src.stem}_nes{suffix}"
    dur = float(duration) if duration else None
    opts = ConvertOptions(
        input_path=src,
        output_path=dest,
        format=fmt,
        mode=mode,
        stems=bool(stems),
        transpose=int(transpose),
        tempo=int(tempo),
        grid=int(grid),
        duration=dur,
        keep_intermediates=False,
    )
    try:
        out = convert(opts, progress=on_log)
    except (PipelineError, FileNotFoundError, ValueError) as exc:
        on_log(f"错误: {exc}")
        return None, None, "\n".join(logs)

    preview = str(out) if out.suffix.lower() in {".wav", ".mp3", ".ogg"} else None
    return preview, str(out), "\n".join(logs) + f"\n完成 → {out}"


def build_app():
    import gradio as gr

    mode_choices = [f"{m}" for m in MODES]
    with gr.Blocks(title="audio2fami") as demo:
        gr.Markdown(
            """
# audio2fami
把任意音频变成 NES 风格 8-bit 音乐。底层用
[basic-pitch](https://github.com/spotify/basic-pitch) 抽 MIDI，
再用 [FamiStudio](https://github.com/BleuBleu/FamiStudio) 做 2A03 芯片渲染。

人声会被压成一条方波；同一时间每个 NES 通道只能有一个音。
            """.strip()
        )
        with gr.Row():
            with gr.Column():
                audio = gr.Audio(
                    label="输入音频（mp3 / wav / flac / ogg / m4a …）",
                    type="filepath",
                )
                fmt = gr.Dropdown(
                    choices=list(OUTPUT_FORMATS),
                    value="mp3",
                    label="输出格式",
                    info="wav / mp3 / ogg 可试听；nsf 给模拟器；txt/fms 是可再编辑的工程（文本格式）",
                )
                mode = gr.Dropdown(
                    choices=mode_choices,
                    value="full",
                    label="编曲模式",
                    info=" / ".join(f"{k}: {v}" for k, v in MODE_HELP.items()),
                )
                stems = gr.Checkbox(
                    label="先用 Demucs 分轨（人声 / 伴奏 / 低音 / 鼓，需额外安装）",
                    value=False,
                )
                with gr.Row():
                    transpose = gr.Slider(-12, 12, value=0, step=1, label="移调（半音）")
                    tempo = gr.Number(value=120, label="量化 BPM", precision=0)
                with gr.Row():
                    grid = gr.Dropdown(
                        choices=[4, 8, 16, 32],
                        value=16,
                        label="量化网格",
                    )
                    duration = gr.Number(
                        value=30,
                        label="只处理前 N 秒（空=全文）",
                    )
                go = gr.Button("转换成 8-bit", variant="primary")
            with gr.Column():
                preview = gr.Audio(label="试听", type="filepath")
                download = gr.File(label="下载结果")
                log = gr.Textbox(label="进度日志", lines=16, interactive=False)

        go.click(
            _convert,
            inputs=[audio, fmt, mode, stems, transpose, tempo, grid, duration],
            outputs=[preview, download, log],
        )
    return demo


def launch(host: str = "0.0.0.0", port: int = 43187) -> None:
    demo = build_app()
    demo.queue().launch(
        server_name=host,
        server_port=port,
        share=False,
        show_error=True,
        inbrowser=False,
    )


if __name__ == "__main__":
    launch()
