"""Cross-platform discovery of ffmpeg / FamiStudio (no real Windows required)."""

from __future__ import annotations

from pathlib import Path

import pytest

from audio2fami.fami_text import write_fami_text
from audio2fami.famistudio import famistudio_cmd, find_famistudio_dir
from audio2fami.midi_cleanup import ChannelSong, SimpleNote
from audio2fami.paths import (
    ENV_FAMISTUDIO,
    ENV_FFMPEG,
    find_ffmpeg,
    is_famistudio_dir,
)


def test_ffmpeg_env_override(tmp_path, monkeypatch):
    fake = tmp_path / "ffmpeg"
    fake.write_text("", encoding="utf-8")
    fake.chmod(0o755)
    monkeypatch.setenv(ENV_FFMPEG, str(fake))
    monkeypatch.delenv("PATH", raising=False)
    found = find_ffmpeg()
    assert found == fake


def test_ffmpeg_explicit_dir(tmp_path):
    exe = tmp_path / "ffmpeg"
    exe.write_text("", encoding="utf-8")
    exe.chmod(0o755)
    assert find_ffmpeg(tmp_path) == exe


def test_famistudio_dir_detects_dll(tmp_path):
    (tmp_path / "FamiStudio.dll").write_bytes(b"x")
    assert is_famistudio_dir(tmp_path)


def test_famistudio_dir_detects_exe(tmp_path):
    (tmp_path / "FamiStudio.exe").write_bytes(b"x")
    assert is_famistudio_dir(tmp_path)


def test_famistudio_cmd_prefers_exe(tmp_path, monkeypatch):
    (tmp_path / "FamiStudio.exe").write_bytes(b"MZ")
    (tmp_path / "FamiStudio.dll").write_bytes(b"x")
    monkeypatch.setenv(ENV_FAMISTUDIO, str(tmp_path))
    cmd = famistudio_cmd()
    assert cmd == [str(tmp_path / "FamiStudio.exe")]


def test_famistudio_cmd_uses_dotnet_for_dll(tmp_path, monkeypatch):
    (tmp_path / "FamiStudio.dll").write_bytes(b"x")
    monkeypatch.setenv(ENV_FAMISTUDIO, str(tmp_path))
    cmd = famistudio_cmd()
    assert cmd[-1] == str(tmp_path / "FamiStudio.dll")
    assert Path(cmd[0]).name.startswith("dotnet")


def test_find_famistudio_missing(monkeypatch, tmp_path):
    monkeypatch.setenv(ENV_FAMISTUDIO, str(tmp_path / "nope"))
    monkeypatch.setattr(
        "audio2fami.famistudio.famistudio_search_dirs",
        lambda explicit=None: [tmp_path / "nope"],
    )
    with pytest.raises(Exception, match="未找到 FamiStudio"):
        find_famistudio_dir()


def test_write_fami_text_utf8_lf_and_unicode_path(tmp_path):
    song = ChannelSong(
        pulse1=[SimpleNote(60, 0.0, 0.25, 80)],
        tempo=120,
        grid=16,
    )
    dest = tmp_path / "工程" / "歌曲.txt"
    write_fami_text(song, dest, name="测试")
    raw = dest.read_bytes()
    assert b"\r\n" not in raw
    text = dest.read_text(encoding="utf-8")
    assert 'Name="测试"' in text
    assert "Project Version=" in text
