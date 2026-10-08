"""End-to-end: audio → stems? → MIDI → NES mapping → FamiStudio export."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from audio2fami.audio import AudioError, normalize_input, probe_duration
from audio2fami.config import (
    AUDIO_FORMATS,
    PROJECT_FORMATS,
    ConvertOptions,
    extension_for,
)
from audio2fami.fami_text import write_fami_text
from audio2fami.fallback import render_format
from audio2fami.famistudio import FamiStudioError, export as fami_export
from audio2fami.logutil import StageLog, default_progress
from audio2fami.midi_cleanup import (
    ChannelSong,
    map_mix,
    map_roles,
    write_cleaned_midi,
)
from audio2fami.stems import StemError, roles_from_stems, separate
from audio2fami.transcribe import TranscribeError, notes_from_wav


class PipelineError(RuntimeError):
    pass


def _stage_count(opts: ConvertOptions) -> int:
    n = 5  # normalize, transcribe, cleanup, text, export
    if opts.stems:
        n += 1
    return n


def convert(
    opts: ConvertOptions,
    progress=None,
) -> Path:
    opts.validate()
    log = StageLog(_stage_count(opts), progress or default_progress)

    work_own = opts.work_dir is None and not opts.keep_intermediates
    work = Path(opts.work_dir or tempfile.mkdtemp(prefix="audio2fami-"))
    work.mkdir(parents=True, exist_ok=True)

    try:
        return _run(opts, work, log)
    finally:
        if work_own:
            shutil.rmtree(work, ignore_errors=True)


def _run(opts: ConvertOptions, work: Path, log: StageLog) -> Path:
    wav = work / "00_input.wav"
    log.step("规范化音频", f"{opts.input_path.name} → 单声道 WAV")
    try:
        normalize_input(
            opts.input_path,
            wav,
            duration=opts.duration,
            sample_rate=22050,
            log=log,
        )
    except AudioError as exc:
        raise PipelineError(str(exc)) from exc

    dur = probe_duration(wav)
    if dur is not None:
        log.info(f"有效时长 {dur:.1f}s")

    role_wavs: dict[str, Path] = {"mix": wav}
    if opts.stems:
        log.step("音轨分离 (Demucs)", "vocals / bass / drums / other")
        try:
            stems = separate(wav, work / "01_stems", log=log)
        except StemError as exc:
            raise PipelineError(str(exc)) from exc
        role_wavs = roles_from_stems(stems)
        if not role_wavs:
            log.warn("分轨结果为空，回退为混合转写")
            role_wavs = {"mix": wav}
        else:
            log.info("分轨: " + ", ".join(f"{k}={v.name}" for k, v in role_wavs.items()))
    else:
        log.info("跳过 Demucs（默认 --no-stems）")

    log.step("音频 → MIDI (basic-pitch)")
    role_notes = {}
    try:
        if set(role_wavs) == {"mix"}:
            raw = work / "02_raw.mid"
            role_notes["mix"] = notes_from_wav(role_wavs["mix"], raw, log=log)
            log.info(f"混合转写 {len(role_notes['mix'])} 个音符")
        else:
            for role, path in role_wavs.items():
                raw = work / f"02_raw_{role}.mid"
                role_notes[role] = notes_from_wav(
                    path, raw, as_drums=(role == "drums"), log=log
                )
                log.info(f"{role}: {len(role_notes[role])} 个音符")
    except TranscribeError as exc:
        raise PipelineError(str(exc)) from exc

    if not any(role_notes.values()):
        raise PipelineError(
            "转写结果为空：basic-pitch 没听到稳定音高。"
            "换一段更有旋律的片段，或加长 --duration。"
        )

    log.step(
        "MIDI 清理 / NES 通道映射",
        f"mode={opts.mode} grid=1/{opts.grid} transpose={opts.transpose}",
    )
    if set(role_notes) == {"mix"}:
        pitched = [n for n in role_notes["mix"] if n.noise_name is None]
        drums = [n for n in role_notes["mix"] if n.noise_name is not None]
        if opts.transpose:
            pitched = [n.transposed(opts.transpose) for n in pitched]
        song = map_mix(
            pitched,
            drums,
            mode=opts.mode,
            tempo=opts.tempo,
            grid_div=opts.grid,
            bass_cutoff=opts.bass_cutoff,
            min_note=opts.min_note,
        )
    else:
        if opts.transpose:
            role_notes = {
                k: [n.transposed(opts.transpose) for n in v]
                for k, v in role_notes.items()
            }
        song = map_roles(
            role_notes,
            mode=opts.mode,
            tempo=opts.tempo,
            grid_div=opts.grid,
            bass_cutoff=opts.bass_cutoff,
            min_note=opts.min_note,
        )

    if song.note_count() == 0:
        raise PipelineError("清理后没有剩下任何音符（阈值过严或转写失败）")

    log.info(
        "通道音符数: "
        f"pulse1={len(song.pulse1)} pulse2={len(song.pulse2)} "
        f"triangle={len(song.triangle)} noise={len(song.noise)}"
    )

    cleaned = work / "03_cleaned.mid"
    write_cleaned_midi(song, cleaned)

    project = work / "04_project.txt"
    log.step("生成 FamiStudio 文本工程", "CLI 不支持 MIDI 导入，改写 .txt")
    write_fami_text(song, project, name=opts.input_path.stem)

    dest = _resolve_dest(opts)
    dest.parent.mkdir(parents=True, exist_ok=True)

    if opts.format in PROJECT_FORMATS:
        log.step("写出可编辑工程", dest.name)
        shutil.copy2(project, dest)
        log.info(
            "FamiStudio CLI 不能写二进制 .fms；此文件是官方文本格式，"
            "可在 FamiStudio 里打开后另存为 .fms。"
        )
        _maybe_copy_intermediates(opts, work, dest, project, cleaned)
        return dest

    log.step(f"FamiStudio 导出 {opts.format.upper()}")
    try:
        fami_export(
            project,
            dest,
            opts.format,
            duration=opts.duration or song.end_time() + 0.5,
            sample_rate=opts.sample_rate,
            famistudio_dir=opts.famistudio_dir,
            log=log,
        )
        log.info(f"完成 → {dest} ({dest.stat().st_size} bytes)")
    except FamiStudioError as exc:
        if opts.format not in AUDIO_FORMATS:
            raise PipelineError(
                f"FamiStudio 导出失败，且 {opts.format} 没有回退渲染器:\n{exc}"
            ) from exc
        log.warn(f"FamiStudio 失败，改用内置 2A03 回退渲染器: {exc}")
        render_format(song, dest, opts.format)
        log.info(f"回退渲染完成 → {dest}")

    _maybe_copy_intermediates(opts, work, dest, project, cleaned)
    return dest


def _resolve_dest(opts: ConvertOptions) -> Path:
    dest = opts.output_path
    want = extension_for(opts.format)
    if dest.suffix.lower().lstrip(".") != want:
        dest = dest.with_suffix(f".{want}")
    return dest


def _maybe_copy_intermediates(
    opts: ConvertOptions,
    work: Path,
    dest: Path,
    project: Path,
    cleaned,
) -> None:
    if not opts.keep_intermediates:
        return
    folder = dest.parent / f"{dest.stem}_intermediates"
    folder.mkdir(parents=True, exist_ok=True)
    for item in work.iterdir():
        target = folder / item.name
        if item.is_file():
            shutil.copy2(item, target)
        elif item.is_dir():
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(item, target)
    # Always keep a sibling project next to audio exports when asked.
    if opts.format not in PROJECT_FORMATS:
        shutil.copy2(project, dest.with_suffix(".txt"))
        shutil.copy2(cleaned, dest.with_suffix(".mid"))


def convert_from_midi(
    midi_path: Path,
    dest: Path,
    *,
    fmt: str = "wav",
    mode: str = "full",
    tempo: int = 120,
    grid: int = 16,
    transpose: int = 0,
    famistudio_dir: Path | None = None,
    progress=None,
) -> Path:
    """Skip transcription — used by tests and `--from-midi`."""
    import pretty_midi

    from audio2fami.midi_cleanup import song_from_pretty_midi

    log = StageLog(3, progress or default_progress)
    log.step("读取 MIDI", midi_path.name)
    pm = pretty_midi.PrettyMIDI(str(midi_path))
    song: ChannelSong = song_from_pretty_midi(
        pm, mode=mode, tempo=tempo, grid=grid, transpose=transpose
    )
    if song.note_count() == 0:
        raise PipelineError("MIDI 里没有可用音符")
    log.step("生成 FamiStudio 文本工程")
    dest.parent.mkdir(parents=True, exist_ok=True)
    project = dest.with_suffix(".txt") if fmt not in PROJECT_FORMATS else dest
    write_fami_text(song, project, name=midi_path.stem)
    if fmt in PROJECT_FORMATS:
        log.step("写出工程")
        return project
    log.step(f"FamiStudio 导出 {fmt}")
    return fami_export(
        project,
        dest,
        fmt,
        duration=song.end_time() + 0.5,
        famistudio_dir=famistudio_dir,
        log=log,
    )
