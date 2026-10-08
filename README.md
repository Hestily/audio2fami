# audio2fami

把任意音频（mp3 / wav / flac / ogg / m4a …）自动转成 **NES 风格 8-bit 音乐**。芯片渲染走 [FamiStudio](https://github.com/BleuBleu/FamiStudio)（MIT，C# / .NET）的官方 Linux 命令行；MIDI 导入在 CLI 里不可用，本工具改写 **FamiStudio 文本工程** 再导出。

[English README](README.en.md)

---

## 一行安装

需要：Linux x86_64、`ffmpeg`、Python **3.9–3.11**（TensorFlow / basic-pitch 不支持 3.12+）、网络。

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

```bash
audio2fami song.mp3 -f mp3 -o out.mp3
audio2fami song.wav -f wav --mode lead --duration 25
audio2fami song.flac -f nsf --mode full --tempo 140 --grid 16 --transpose 2
audio2fami song.m4a -f txt --keep-intermediates   # 可在 FamiStudio 里再改
audio2fami --from-midi cleaned.mid -f wav -o out.wav
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

```bash
audio2fami ui --port 43187
# 浏览器打开 http://127.0.0.1:43187
```

上传音频 → 下拉选择格式和编曲模式 → 点「转换成 8-bit」→ 试听 / 下载。右侧（下方）进度日志按阶段刷新。不依赖 Gradio，避免和 TensorFlow 的依赖打架。

---

## 输出格式（已在 Linux 上核实）

FamiStudio **4.5.2** 命令行：

```
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
5. **写成 FamiStudio 文本**，调用  
   `dotnet FamiStudio.dll project.txt wav-export out.wav`（或 `mp3-export` / `ogg-export` / `nsf-export`）。

---

## 限制（先读这个）

- **人声会变成一条方波。** basic-pitch 抽的是音高，不是歌词或音色。
- **同一时刻每个 NES 通道只能一个音。** 和弦会被压成 1–2 条线 + 一条低音。
- **鼓是近似。** 噪声通道只有一种「沙沙」音色，靠音高/包络区分踩镲和底鼓。
- **没有 DPCM 采样**（除非你事后在 FamiStudio 里自己贴）。
- **速度是量化网格，不是原曲精确 BPM。** `--tempo` 对不齐时，旋律会「电子琴化」。
- **basic-pitch 第一次运行会下载模型**，CPU 上二三十秒音频可能要一两分钟。
- 已知环境坑：必须 **Python 3.9–3.11**、`numpy<2`、`setuptools<81`（resampy 还在用 `pkg_resources`）。

---

## 测试与样例

公共领域样例：Erik Satie《Gymnopédie No.1》，[Teknopazzo 的 CC0 录音](https://commons.wikimedia.org/wiki/File:Gymnopedie_No._1..ogg)，截取前 30 秒。

```bash
python scripts/download_sample.py
pytest -q
# 完整转写（会跑 basic-pitch，较慢）：
pytest -q -m e2e
```

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

FamiStudio 二进制请按上游 LICENSE 使用；`setup.sh` 会下载官方 Linux AMD64 包，不进 git。
