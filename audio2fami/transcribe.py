"""Audio → MIDI via Spotify basic-pitch."""

from __future__ import annotations

from pathlib import Path

import pretty_midi

from audio2fami.logutil import StageLog
from audio2fami.midi_cleanup import SimpleNote, collect_notes


class TranscribeError(RuntimeError):
    pass


def _predict(wav: Path):
    # Imported lazily: TensorFlow startup is slow and noisy.
    try:
        from basic_pitch.inference import predict
    except ImportError as exc:
        raise TranscribeError(
            "未安装 basic-pitch / TensorFlow。请运行 ./setup.sh"
        ) from exc
    try:
        _model_output, midi_data, _events = predict(str(wav))
    except Exception as exc:  # noqa: BLE001 — surface TF/model errors cleanly
        raise TranscribeError(f"basic-pitch 转写失败: {exc}") from exc
    if midi_data is None:
        raise TranscribeError("basic-pitch 没有返回 MIDI")
    return midi_data


def transcribe_wav(wav: Path, raw_midi: Path | None, log: StageLog | None = None):
    if log:
        log.info(f"basic-pitch 分析 {wav.name}（首次运行会下载模型）")
    pm = _predict(wav)
    if raw_midi is not None:
        raw_midi.parent.mkdir(parents=True, exist_ok=True)
        pm.write(str(raw_midi))
    return pm


def notes_from_wav(
    wav: Path,
    raw_midi: Path | None,
    *,
    as_drums: bool = False,
    log: StageLog | None = None,
) -> list[SimpleNote]:
    pm: pretty_midi.PrettyMIDI = transcribe_wav(wav, raw_midi, log=log)
    if as_drums:
        # Percussive stem: treat every note as a drum hit, even if BP
        # did not mark the track as a drum kit.
        notes = collect_notes(pm, drums=False) + collect_notes(pm, drums=True)
        for n in notes:
            if n.noise_name is None:
                n.noise_name = "D4"
        return notes
    return collect_notes(pm, drums=False) + collect_notes(pm, drums=True)
