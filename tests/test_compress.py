import shutil
import subprocess
from pathlib import Path

import pytest

from franky.catalog.compress import (
    CompressionError,
    compress,
    compress_oversized,
    pick_bitrate,
    probe_duration,
)
from franky.services.audio import AudioSender, AudioUnavailableError

MB = 1024 * 1024


@pytest.mark.parametrize(
    ("minutes", "expected"),
    [
        (50, 96),  # обычный выпуск: 96 кбит/с ≈ 34 МБ
        (75, 80),
        (95, 64),
        (110, 56),
        (130, 48),
    ],
)
def test_pick_bitrate_fits_limit(minutes: int, expected: int) -> None:
    kbps = pick_bitrate(minutes * 60, max_bytes=48 * MB)
    assert kbps == expected
    assert kbps * 1000 / 8 * minutes * 60 <= 48 * MB


def test_pick_bitrate_rejects_too_long_and_broken() -> None:
    with pytest.raises(CompressionError):
        pick_bitrate(300 * 60, max_bytes=48 * MB)
    with pytest.raises(CompressionError):
        pick_bitrate(0)


async def test_sender_refuses_oversized_upload(tmp_path: Path) -> None:
    from franky.db.models import Episode

    (tmp_path / "1.mp3").write_bytes(b"x" * 2048)
    sender = AudioSender(bot=None, audio_dir=tmp_path, upload_limit=1024)  # type: ignore[arg-type]
    with pytest.raises(AudioUnavailableError, match="больше 50 МБ"):
        sender._local_file(Episode(id=1, audio_file="1.mp3"))


needs_ffmpeg = pytest.mark.skipif(
    not (shutil.which("ffmpeg") and shutil.which("ffprobe")), reason="нужен ffmpeg"
)


def make_mp3(path: Path, *args: str) -> Path:
    subprocess.run(
        ["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=60", *args,
         str(path)],
        check=True,
    )  # fmt: skip
    return path


def read_tags(path: Path) -> str:
    return subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format_tags", "-of", "json", str(path)],
        capture_output=True, text=True, check=True,
    ).stdout  # fmt: skip


@pytest.fixture
def loud_mp3(tmp_path: Path) -> Path:
    """60 секунд тона в 320 кбит/с (≈2.3 МБ) с тегом-спойлером."""
    return make_mp3(tmp_path / "7.mp3", "-b:a", "320k", "-metadata", "title=Маяковский")


@needs_ffmpeg
async def test_compress_real_file(loud_mp3: Path) -> None:
    size = loud_mp3.stat().st_size
    assert size > 2 * MB

    assert await compress_oversized(loud_mp3.parent, max_bytes=1 * MB) == 1
    assert loud_mp3.stat().st_size <= 1 * MB
    assert (loud_mp3.parent / "originals" / "7.mp3").stat().st_size == size
    assert 59 < await probe_duration(loud_mp3) < 61
    assert "Маяковский" not in read_tags(loud_mp3)  # теги вычищены
    assert await compress_oversized(loud_mp3.parent, max_bytes=1 * MB) == 0  # повторно не трогаем


@needs_ffmpeg
async def test_compress_fails_when_cannot_fit(loud_mp3: Path) -> None:
    with pytest.raises(CompressionError):
        await compress(loud_mp3, max_bytes=100_000)
    assert loud_mp3.exists()  # оригинал на месте
