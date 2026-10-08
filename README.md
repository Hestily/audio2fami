# audio2fami

把任意音频（mp3 / wav / flac / ogg / m4a …）自动转成 **NES 风格 8-bit 音乐**。芯片渲染走 [FamiStudio](https://github.com/BleuBleu/FamiStudio)（MIT，C# / .NET）官方命令行；MIDI 导入在 CLI 里不可用，本工具改写 **FamiStudio 文本工程** 再导出。支持 **Windows 10/11 x64**（原生，不用 WSL）和 Linux。

[English README](README.en.md)

---

## 一行安装

Python **3.9–3.11**（TensorFlow / basic-pitch 不支持 3.12+）、网络。Windows 不要用 WSL/Docker，直接跑下面的 `setup.cmd`。

### Windows 10 / 11 x64

资源管理器里**双击 `setup.cmd`**，或在 cmd / PowerShell 里：

```bat
setup.cmd
REM 可选：setup.cmd -Stems     （额外装 Demucs，体积大）
```

PowerShell 若被执行策略拦住，**不要**直接 `.\setup.ps1`，用 `setup.cmd`（它会 `-ExecutionPolicy Bypass`）。装完后：

```bat
audio2fami.cmd samples\gymnopedie_30s.wav -f mp3 -o artifacts\out.mp3 --duration 25
start-ui.cmd
```

安装器会：找或安装 Python 3.11（uv / winget / python.org）、建 `.venv`、按 `requirements.txt` 装依赖（`numpy<2`、`setuptools<81`）、把便携 **ffmpeg** 放到 `third_party\ffmpeg`、安装用户级 **.NET 8 运行时**（Windows 便携版 FamiStudio **不是**自包含，官方文档要求 Runtime 8.0）、下载 [FamiStudio 4.5.2 WinPortableExe](https://github.com/BleuBleu/FamiStudio/releases/tag/4.5.2) 到 `third_party\FamiStudio`。

覆盖路径（CLI 与环境变量等价）：

```bat
set AUDIO2FAMI_FAMISTUDIO=C:\tools\FamiStudio
set AUDIO2FAMI_FFMPEG=C:\tools\ffmpeg\ffmpeg.exe
audio2fami.cmd song.mp3 -f wav --famistudio-dir C:\tools\FamiStudio --ffmpeg C:\tools\ffmpeg\ffmpeg.exe
```

### Linux x86_64

```bash
chmod +x setup.sh
./setup.sh                  # FamiStudio 4.5.2 + .NET 8 + Python 依赖
# ./setup.sh --stems        # 额外装 Demucs（体积大，仅 --stems 时需要）
source .venv/bin/activate
export DOTNET_ROOT="$HOME/.dotnet" PATH="$HOME/.dotnet:$PATH"
```

或用 Docker：

```bash
docker build -t audio2fami .
docker run --rm -p 43187:43187 audio2fami
# 或批处理：
docker run --rm -v "$PWD:/data" audio2fami \
  audio2fami /data/song.mp3 -f mp3 -o /data/out.mp3 --duration 30
```

---

## 命令行

Linux / macOS 风格（已 `source .venv/bin/activate`）：

```bash
audio2fami song.mp3 -f mp3 -o out.mp3
audio2fami song.wav -f wav --mode lead --duration 25
audio2fami song.flac -f nsf --mode full --tempo 140 --grid 16 --transpose 2
audio2fami song.m4a -f txt --keep-intermediates   # 可在 FamiStudio 里再改
audio2fami --from-midi cleaned.mid -f wav -o out.wav
```

Windows **cmd**：

```bat
audio2fami.cmd song.mp3 -f mp3 -o out.mp3
audio2fami.cmd "D:\音乐\曲子.wav" -f wav --mode lead --duration 25
audio2fami.cmd song.flac -f nsf --mode full --tempo 140 --grid 16
```

Windows **PowerShell**：

```powershell
.\audio2fami.cmd song.mp3 -f mp3 -o out.mp3
.\audio2fami.cmd .\samples\gymnopedie_30s.wav -f nsf --duration 20
```

常用参数：

| 参数 | 含义 |
| --- | --- |
| `-f / --format` | `wav` `mp3` `ogg` `nsf` `txt` `fms`（非法值会报错） |
| `--mode` | `lead` 仅主旋律；`harmony` 主旋律+和声；`full` 四声部（默认） |
| `--stems` / `--no-stems` | 是否先 Demucs 分轨（默认不分） |
| `--transpose` | 移调，半音 |
| `--tempo` | 量化 BPM（默认 120） |
| `--grid` | `4` / `8` / `16` / `32` 音符网格 |
| `--duration` | 只处理前 N 秒 |
| `--keep-intermediates` | 保留分轨、原始 MIDI、清理后 MIDI、`.txt` 工程 |

---

## 本地网页

Linux：

```bash
audio2fami ui --port 43187
# 浏览器打开 http://127.0.0.1:43187
```

Windows：双击 `start-ui.cmd`（会启动服务并打开浏览器）。或：

```bat
audio2fami.cmd ui --host 127.0.0.1 --port 43187
```

上传音频 → 下拉选择格式和编曲模式 → 点「转换成 8-bit」→ 试听 / 下载。不依赖 Gradio，避免和 TensorFlow 的依赖打架。

---

## 输出格式

FamiStudio **4.5.2** 命令行：

```
REM Windows 便携版
FamiStudio.exe <input> <command> <output> [-options]
REM Linux（以及没有 exe 时）
dotnet FamiStudio.dll <input> <command> <output> [-options]
```

| 格式 | CLI 命令 | 本工具 | 说明 |
| --- | --- | --- | --- |
| WAV | `wav-export` | 支持 | `-wav-export-rate:11025\|22050\|44100\|48000` |
| MP3 | `mp3-export` | 支持 | 内置 ShineMp3，44100/48000 |
| OGG | `ogg-export` | 支持 | 桌面版才有，Linux CLI 可用 |
| NSF | `nsf-export` | 支持 | 给 NSF 播放器 / 模拟器 |
| 文本工程 | （我们生成） | 支持 `txt` / `fms` | 见下 |
| ROM / FDS / 汇编 | CLI 有 | 未封装 | 需要可自行对 `.txt` 再调 CLI |

**CLI 支持的输入**：`.fms`、FamiStudio `.txt`、FamiTracker `.ftm` / `.txt`、`.nsf` / `.nsfe`。  
**不支持 MIDI。** GUI 里可以导入 MIDI，但 `CommandLineInterface.cs` 没有这条路径。本工具把清理后的音符写成 FamiStudio 文本（`TempoMode=FamiTracker`），再交给 CLI 导出。

**关于 `.fms`**：CLI **不能写出二进制 `.fms`**。选 `fms` 或 `txt` 时得到的是官方文本工程，可直接用 FamiStudio 打开，再「另存为」`.fms` 手改。版本号必须对上当前主/次版本（本仓库按 4.5.2 写）。

FamiStudio 导出失败时，`wav` / `mp3` / `ogg` 会落到内置 2A03 回退渲染器（方波 + 三角波 + 噪声），并在日志里标明。

---

## 流水线怎么走

1. **ffmpeg** 把任意容器解成单声道 WAV，可按 `--duration` 截断。
2. **Demucs**（可选，[adefossez/demucs](https://github.com/adefossez/demucs)）拆出人声 / 伴奏 / 低音 / 鼓。
3. **basic-pitch**（[spotify/basic-pitch](https://github.com/spotify/basic-pitch)）音频 → MIDI。
4. **清理**：量化到网格、丢掉极短音、把复音压到 NES 通道——2 个脉冲 + 三角波 + 噪声（DPCM 默认不用）。
   - 主旋律 → Pulse 1（25% 方波）
   - 和声 → Pulse 2（50% 方波）
   - 低音 → Triangle
   - 鼓 → Noise（GM 打击乐映射到噪声音高）
5. **写成 FamiStudio 文本**（UTF-8、LF 换行），调用  
   `FamiStudio.exe project.txt wav-export out.wav`（Windows）或  
   `dotnet FamiStudio.dll project.txt wav-export out.wav`（Linux）。

---

## 限制（先读这个）

- **人声会变成一条方波。** basic-pitch 抽的是音高，不是歌词或音色。
- **同一时刻每个 NES 通道只能一个音。** 和弦会被压成 1–2 条线 + 一条低音。
- **鼓是近似。** 噪声通道只有一种「沙沙」音色，靠音高/包络区分踩镲和底鼓。
- **没有 DPCM 采样**（除非你事后在 FamiStudio 里自己贴）。
- **速度是量化网格，不是原曲精确 BPM。** `--tempo` 对不齐时，旋律会「电子琴化」。
- **basic-pitch 第一次运行会下载模型**，CPU 上二三十秒音频可能要一两分钟。
- 已知环境坑：必须 **Python 3.9–3.11**、`numpy<2`、`setuptools<81`（resampy 还在用 `pkg_resources`）。

### Windows 排障

| 现象 | 处理 |
| --- | --- |
| `无法加载文件 setup.ps1，因为在此系统上禁止运行脚本` | 用 **`setup.cmd`**，不要直接跑 ps1 |
| SmartScreen / 杀毒拦截 FamiStudio | 属性 → 解除锁定；`setup.ps1` 会对下载的 exe/dll 做 `Unblock-File` |
| `未找到 ffmpeg` | 确认 `third_party\ffmpeg\ffmpeg.exe`，或设 `AUDIO2FAMI_FFMPEG` |
| `未找到 .NET` / FamiStudio 一闪退出 | 安装 [.NET 8 Runtime](https://dotnet.microsoft.com/download/dotnet/8.0) x64，或重跑 setup.cmd |
| `未找到 FamiStudio` | 确认 `third_party\FamiStudio\FamiStudio.exe`（或 `.dll`），或设 `AUDIO2FAMI_FAMISTUDIO` |
| 路径太长（>260 字符） | 把仓库放到较短目录，如 `C:\src\audio2fami`；可在系统里打开「长路径」 |
| Python 3.12+ 装上了 | 必须 3.9–3.11。setup 会优先装 3.11 |
| 中文文件名 | CLI 用 Unicode 参数传给 ffmpeg / FamiStudio；若仍失败，先复制到英文路径 |
| `start-ui.cmd` 没有页面 | 等终端出现 `Uvicorn running`，浏览器打开 http://127.0.0.1:43187 |

---

## 测试与样例

公共领域样例：Erik Satie《Gymnopédie No.1》，[Teknopazzo 的 CC0 录音](https://commons.wikimedia.org/wiki/File:Gymnopedie_No._1..ogg)，截取前 30 秒。

```bash
python scripts/download_sample.py
pytest -q
# 完整转写（会跑 basic-pitch，较慢）：
pytest -q -m e2e
```

CI：`.github/workflows/ci.yml` 在 `ubuntu-latest` 跑全部非 basic-pitch 测试 + FamiStudio 导出，在 `windows-latest` 跑单测以及 `--from-midi` 的 FamiStudio e2e（跳过 basic-pitch 样例，避免 Windows runner 上 TensorFlow 过慢）。本仓库开发机是 Linux，**没有在真实 Windows 桌面上点过 setup.cmd**。

生成的试听文件在 `artifacts/gymnopedie_nes.mp3`（以及 wav / nsf / txt）。

---

## 许可证

| 组件 | 许可 |
| --- | --- |
| 本仓库（audio2fami） | MIT |
| [FamiStudio](https://github.com/BleuBleu/FamiStudio) | MIT |
| [basic-pitch](https://github.com/spotify/basic-pitch) | Apache-2.0 |
| [Demucs](https://github.com/adefossez/demucs) | MIT（facebookresearch/demucs 已归档，请用这个维护中的 fork） |
| 样例录音 | CC0（Wikimedia Commons） |

FamiStudio 二进制请按上游 LICENSE 使用；`setup.sh` / `setup.cmd` 会下载官方包到 `third_party/`，不进 git。

Windows 便携版 **需要本机 .NET 8 运行时**（与 Linux 的 `dotnet FamiStudio.dll` 相同依赖）；安装器不是自包含单文件。
