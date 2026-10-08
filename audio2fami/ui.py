"""Minimal local web UI: upload audio, convert, play/download."""

from __future__ import annotations

import os
import tempfile
import traceback
from pathlib import Path

from audio2fami.config import MODE_HELP, MODES, OUTPUT_FORMATS, ConvertOptions
from audio2fami.pipeline import PipelineError, convert

PAGE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>audio2fami</title>
  <style>
    :root { color-scheme: dark; }
    body { font-family: "Noto Sans CJK SC", "Noto Sans SC", "Noto Sans",
           ui-sans-serif, system-ui, sans-serif; margin: 0;
           background: #12141a; color: #e8e6e3; }
    main { max-width: 880px; margin: 0 auto; padding: 28px 16px 64px; }
    h1 { font-size: 1.7rem; margin: 0 0 8px; letter-spacing: -0.02em; }
    .sub { color: #9aa3b2; margin-bottom: 24px; line-height: 1.5; }
    form, .out { background: #1b1f2a; border: 1px solid #2c3344; border-radius: 12px;
                 padding: 18px; margin-bottom: 16px; }
    label { display: block; font-size: 0.85rem; color: #c5c9d3; margin: 12px 0 6px; }
    input, select { width: 100%; box-sizing: border-box; background: #0f1218;
                    color: #e8e6e3; border: 1px solid #3a4254; border-radius: 8px;
                    padding: 10px; }
    .row { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
    @media (max-width: 640px) { .row { grid-template-columns: 1fr; } }
    button { margin-top: 16px; width: 100%; background: #e2a34a; color: #1a1206;
             border: 0; border-radius: 8px; padding: 12px; font-weight: 700;
             cursor: pointer; font-size: 1rem; }
    button:disabled { opacity: 0.6; cursor: wait; }
    pre { white-space: pre-wrap; font-size: 0.8rem; color: #b8c0cc;
          background: #0f1218; padding: 12px; border-radius: 8px; min-height: 8rem; }
    audio { width: 100%; margin: 10px 0; }
    a.dl { color: #e2a34a; }
  </style>
</head>
<body>
<main>
  <h1>audio2fami</h1>
  <p class="sub">Drop in any audio file, pick a format, get NES-style 8-bit music.
  FamiStudio renders the 2A03 chip in the background.
  Vocals become a single square-wave line; each NES channel is monophonic.<br/>
  上传音频即可。人声会变成一条方波；每个通道同时只能一个音。</p>
  <form id="f">
    <label>Audio / 输入音频 (mp3, wav, flac, ogg, m4a…)</label>
    <input type="file" name="audio" accept="audio/*,.mp3,.wav,.flac,.ogg,.m4a,.aac" required/>
    <div class="row">
      <div>
        <label>Output format / 输出格式</label>
        <select name="format">
          <option value="mp3" selected>mp3 (playable)</option>
          <option value="wav">wav</option>
          <option value="ogg">ogg</option>
          <option value="nsf">nsf (emulator)</option>
          <option value="txt">txt (FamiStudio text project)</option>
          <option value="fms">fms (same text project; Save As .fms in the app)</option>
        </select>
      </div>
      <div>
        <label>Arrangement / 编曲模式</label>
        <select name="mode">
          <option value="full" selected>full — lead + harmony + bass + drums</option>
          <option value="harmony">harmony — lead + harmony</option>
          <option value="lead">lead — melody only</option>
        </select>
      </div>
    </div>
    <div class="row">
      <div>
        <label>Quantize BPM / 量化速度</label>
        <input type="number" name="tempo" value="120" min="32" max="300"/>
      </div>
      <div>
        <label>Grid / 量化网格</label>
        <select name="grid">
          <option value="8">8 (eighths)</option>
          <option value="16" selected>16 (sixteenths)</option>
          <option value="32">32 (thirty-seconds)</option>
          <option value="4">4 (quarters)</option>
        </select>
      </div>
    </div>
    <div class="row">
      <div>
        <label>Transpose / 移调 (semitones)</label>
        <input type="number" name="transpose" value="0" min="-24" max="24"/>
      </div>
      <div>
        <label>Limit / 只处理前 N 秒 (empty = all)</label>
        <input type="number" name="duration" value="30" min="1" step="1"/>
      </div>
    </div>
    <label><input type="checkbox" name="stems" value="1" style="width:auto"/>
      Separate stems with Demucs / 先分轨（需额外安装）</label>
    <button type="submit" id="go">Convert to 8-bit / 转换成 8-bit</button>
  </form>
  <div class="out">
    <pre id="log">Waiting… 等待转换</pre>
    <audio id="player" controls hidden></audio>
    <p id="dlwrap" hidden><a class="dl" id="dl" href="#">下载结果</a></p>
  </div>
</main>
<script>
const f = document.getElementById('f');
const log = document.getElementById('log');
const go = document.getElementById('go');
const player = document.getElementById('player');
const dl = document.getElementById('dl');
const dlwrap = document.getElementById('dlwrap');
f.addEventListener('submit', async (e) => {
  e.preventDefault();
  go.disabled = true;
  log.textContent = '开始转换，阶段日志会写在这里…\\n';
  player.hidden = true; dlwrap.hidden = true;
  const body = new FormData(f);
  try {
    const res = await fetch('/convert', { method: 'POST', body });
    const data = await res.json();
    log.textContent = data.log || data.error || JSON.stringify(data);
    if (data.url) {
      dl.href = data.url;
      dl.textContent = '下载 ' + (data.name || '结果');
      dlwrap.hidden = false;
      if (data.preview) {
        player.src = data.url;
        player.hidden = false;
      }
    }
  } catch (err) {
    log.textContent += '\\n请求失败: ' + err;
  } finally {
    go.disabled = false;
  }
});
</script>
</body>
</html>
"""


def build_app():
    from starlette.applications import Starlette
    from starlette.responses import FileResponse, HTMLResponse, JSONResponse
    from starlette.routing import Route

    out_root = Path(tempfile.gettempdir()) / "audio2fami-ui"
    out_root.mkdir(parents=True, exist_ok=True)

    async def index(_request):
        return HTMLResponse(PAGE)

    async def convert_route(request):
        form = await request.form()
        upload = form.get("audio")
        if upload is None or not getattr(upload, "filename", None):
            return JSONResponse({"error": "请先上传一段音频。"}, status_code=400)
        fmt = str(form.get("format") or "mp3")
        mode = str(form.get("mode") or "full")
        if fmt not in OUTPUT_FORMATS:
            return JSONResponse({"error": f"不支持的格式: {fmt}"}, status_code=400)
        if mode not in MODES:
            return JSONResponse({"error": f"不支持的模式: {mode}"}, status_code=400)

        logs: list[str] = []

        def on_log(msg: str) -> None:
            logs.append(msg)

        suffix = Path(upload.filename).suffix or ".bin"
        src = out_root / f"in{suffix}"
        data = await upload.read()
        src.write_bytes(data)

        tempo = int(form.get("tempo") or 120)
        grid = int(form.get("grid") or 16)
        transpose = int(form.get("transpose") or 0)
        duration_raw = form.get("duration")
        duration = float(duration_raw) if duration_raw else None
        stems = str(form.get("stems") or "") in {"1", "on", "true"}

        dest = out_root / f"out.{ 'txt' if fmt in ('txt', 'fms') else fmt }"
        opts = ConvertOptions(
            input_path=src,
            output_path=dest,
            format=fmt,
            mode=mode,
            stems=stems,
            transpose=transpose,
            tempo=tempo,
            grid=grid,
            duration=duration,
        )
        try:
            out = convert(opts, progress=on_log)
        except (PipelineError, FileNotFoundError, ValueError) as exc:
            on_log(f"错误: {exc}")
            return JSONResponse({"error": str(exc), "log": "\n".join(logs)}, status_code=400)
        except Exception as exc:  # noqa: BLE001
            on_log(traceback.format_exc())
            return JSONResponse({"error": str(exc), "log": "\n".join(logs)}, status_code=500)

        token = out.name
        public = out_root / token
        if public.resolve() != out.resolve():
            public.write_bytes(out.read_bytes())
        return JSONResponse(
            {
                "url": f"/download/{token}",
                "name": out.name,
                "preview": out.suffix.lower() in {".wav", ".mp3", ".ogg"},
                "log": "\n".join(logs) + f"\n完成 → {out.name}",
            }
        )

    async def download(request):
        name = Path(request.path_params["name"]).name
        path = out_root / name
        if not path.is_file():
            return JSONResponse({"error": "文件不存在"}, status_code=404)
        return FileResponse(path, filename=name)

    return Starlette(
        routes=[
            Route("/", index),
            Route("/convert", convert_route, methods=["POST"]),
            Route("/download/{name}", download),
        ]
    )


def launch(host: str = "0.0.0.0", port: int = 43187) -> None:
    import uvicorn

    os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")
    os.environ.setdefault("PYTHONUTF8", "1")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    url = f"http://127.0.0.1:{port}" if host in {"0.0.0.0", "::"} else f"http://{host}:{port}"
    print(f"audio2fami UI  {url}", flush=True)
    print("模式说明: " + " | ".join(f"{k}={v}" for k, v in MODE_HELP.items()), flush=True)
    if os.environ.get("AUDIO2FAMI_OPEN_BROWSER", "").strip() in {"1", "true", "yes"}:
        import threading
        import webbrowser

        threading.Timer(1.2, lambda: webbrowser.open(url)).start()
    uvicorn.run(build_app(), host=host, port=port, log_level="info")


if __name__ == "__main__":
    launch()
