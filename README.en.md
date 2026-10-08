# audio2fami

Drop in any audio file ffmpeg can read, pick an output format, get NES-style 8-bit music. Chip rendering is [FamiStudio](https://github.com/BleuBleu/FamiStudio) (MIT, C# / .NET) driven **headlessly** on Linux. MIDI is **not** a CLI input — the tool writes a FamiStudio text project and exports from that.

Chinese README (primary): [README.md](README.md)

## Install

```bash
./setup.sh
source .venv/bin/activate
export DOTNET_ROOT="$HOME/.dotnet" PATH="$HOME/.dotnet:$PATH"
```

Python **3.9–3.11** only (`numpy<2`, `setuptools<81`). Docker: `docker build -t audio2fami . && docker run --rm -p 43187:43187 audio2fami`.

## Usage

```bash
audio2fami song.mp3 -f mp3 -o out.mp3
audio2fami ui --port 43187   # tiny local web UI (Starlette), not Gradio
```

Formats verified on Linux 4.5.2: `wav`, `mp3`, `ogg`, `nsf`. `txt` / `fms` write the official text project (binary `.fms` cannot be saved from the CLI; open the text file in FamiStudio and Save As).

## How FamiStudio is driven

```
dotnet third_party/FamiStudio/FamiStudio.dll project.txt wav-export out.wav \
  -export-songs:0 -wav-export-rate:44100
dotnet … project.txt mp3-export out.mp3 -mp3-export-rate:44100 -mp3-export-bitrate:192
dotnet … project.txt nsf-export out.nsf -nsf-export-mode:ntsc
```

No display required. Help: `dotnet FamiStudio.dll -help`.

## Licenses

audio2fami MIT · FamiStudio MIT · basic-pitch Apache-2.0 · Demucs MIT · sample recording CC0.
