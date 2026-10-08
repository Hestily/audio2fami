# audio2fami

Drop in any audio file ffmpeg can read, pick an output format, get NES-style 8-bit music. Chip rendering is [FamiStudio](https://github.com/BleuBleu/FamiStudio) (MIT, C# / .NET) driven **headlessly**. MIDI is **not** a CLI input — the tool writes a FamiStudio text project and exports from that.

Native **Windows 10/11 x64** (no WSL) and Linux. Chinese README (primary): [README.md](README.md)

## Install

Python **3.9–3.11** only (`numpy<2`, `setuptools<81`).

### Windows 10 / 11 x64

Double-click `setup.cmd`, or from cmd/PowerShell:

```bat
setup.cmd
REM optional: setup.cmd -Stems
```

If PowerShell execution policy blocks scripts, use **`setup.cmd`** (it runs `setup.ps1` with `-ExecutionPolicy Bypass`). Do not run `.\setup.ps1` directly.

Then:

```bat
audio2fami.cmd samples\gymnopedie_30s.wav -f mp3 -o artifacts\out.mp3 --duration 25
start-ui.cmd
```

The installer installs Python 3.11 if needed (uv / winget / python.org), creates `.venv`, installs pinned deps, drops a portable **ffmpeg** into `third_party\ffmpeg`, installs a user-local **.NET 8 runtime** (the Windows FamiStudio portable build is **not** self-contained), and downloads **FamiStudio 4.5.2 WinPortableExe** into `third_party\FamiStudio`.

Overrides: `AUDIO2FAMI_FAMISTUDIO`, `AUDIO2FAMI_FFMPEG`, or `--famistudio-dir` / `--ffmpeg`.

### Linux

```bash
./setup.sh
source .venv/bin/activate
export DOTNET_ROOT="$HOME/.dotnet" PATH="$HOME/.dotnet:$PATH"
```

Docker: `docker build -t audio2fami . && docker run --rm -p 43187:43187 audio2fami`.

## Usage

```bash
audio2fami song.mp3 -f mp3 -o out.mp3
audio2fami ui --port 43187
```

Windows:

```bat
audio2fami.cmd song.mp3 -f mp3 -o out.mp3
audio2fami.cmd ui --host 127.0.0.1 --port 43187
start-ui.cmd
```

Formats: `wav`, `mp3`, `ogg`, `nsf`. `txt` / `fms` write the official text project (binary `.fms` cannot be saved from the CLI; open the text file in FamiStudio and Save As).

## How FamiStudio is driven

Windows portable:

```
FamiStudio.exe project.txt wav-export out.wav -export-songs:0 -wav-export-rate:44100
```

Linux:

```
dotnet third_party/FamiStudio/FamiStudio.dll project.txt wav-export out.wav \
  -export-songs:0 -wav-export-rate:44100
```

Always pass **absolute paths**. Help: `FamiStudio.exe -help` or `dotnet FamiStudio.dll -help`.

## Windows troubleshooting

- Execution policy → use `setup.cmd`
- SmartScreen on FamiStudio → Unblock in file Properties (`setup.ps1` also `Unblock-File`s downloads)
- Missing ffmpeg / FamiStudio / .NET 8 → re-run `setup.cmd`, or set the env vars above
- Paths longer than 260 characters → clone to a short directory
- Need Python 3.11, not 3.12+

## Licenses

audio2fami MIT · FamiStudio MIT · basic-pitch Apache-2.0 · Demucs MIT · sample recording CC0.
