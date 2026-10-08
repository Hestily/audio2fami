# Sample outputs

Public-domain clip: Erik Satie, *Gymnopédie No.1*, CC0 recording by Teknopazzo
(https://commons.wikimedia.org/wiki/File:Gymnopedie_No._1..ogg), first 25 seconds.

All audio files below were rendered by **FamiStudio 4.5.2** on Linux via:

```
dotnet FamiStudio.dll project.txt wav-export out.wav -export-songs:0 -wav-export-rate:44100
dotnet FamiStudio.dll project.txt mp3-export out.mp3 -mp3-export-rate:44100 -mp3-export-bitrate:192
dotnet FamiStudio.dll project.txt nsf-export out.nsf -nsf-export-mode:ntsc
```

| File | What it is |
| --- | --- |
| `gymnopedie_nes.mp3` | 44.1 kHz / 192 kbps, FamiStudio ShineMp3 |
| `gymnopedie_nes.wav` | 44.1 kHz 16-bit mono PCM |
| `gymnopedie_nes.ogg` | 44.1 kHz Vorbis (if present) |
| `gymnopedie_nes.nsf` | NTSC NSF for emulators |
| `gymnopedie_nes.txt` | FamiStudio text project (open in FamiStudio, Save As `.fms`) |
| `ui.png` | Local web UI (idle form) |
| `audio2fami-conversion-complete.webp` | Same UI after converting the sample to mp3 (player + download) |
