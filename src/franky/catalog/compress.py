"""Сжатие выпусков, которые не влезают в лимит Bot API на загрузку (50 МБ)."""

import asyncio
import json
import math
import shutil
from dataclasses import dataclass
from pathlib import Path

import structlog

log = structlog.get_logger(__name__)

# С запасом от 50 МБ: контейнер mp3 и округления битрейта дают пару процентов сверху.
MAX_BYTES = 48 * 1024 * 1024
# Для разговорного радио 96 кбит/с не отличить от 128, 64 — ещё вполне прилично.
BITRATES_KBPS = (96, 80, 64, 56, 48)
ORIGINALS_DIR = "originals"


class CompressionError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class CompressResult:
    path: Path
    bitrate_kbps: int
    size_before: int
    size_after: int


def pick_bitrate(duration_seconds: float, max_bytes: int = MAX_BYTES) -> int:
    """Наибольший битрейт из BITRATES_KBPS, при котором файл влезает в max_bytes."""
    if duration_seconds <= 0:
        raise CompressionError("Не удалось определить длительность аудио")
    limit_kbps = math.floor(max_bytes * 8 / duration_seconds / 1000)
    for kbps in BITRATES_KBPS:
        if kbps <= limit_kbps:
            return kbps
    raise CompressionError(
        f"Выпуск слишком длинный ({duration_seconds / 60:.0f} мин): "
        f"даже {BITRATES_KBPS[-1]} кбит/с не влезут в лимит"
    )


def needs_compression(path: Path, max_bytes: int = MAX_BYTES) -> bool:
    return path.stat().st_size > max_bytes


async def _run(*args: str) -> bytes:
    proc = await asyncio.create_subprocess_exec(
        *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        tail = stderr.decode(errors="replace").strip().splitlines()[-3:]
        raise CompressionError(f"{args[0]} завершился с кодом {proc.returncode}: {tail}")
    return stdout


async def probe_duration(path: Path) -> float:
    out = await _run(
        "ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)
    )
    return float(json.loads(out)["format"]["duration"])


async def compress(path: Path, max_bytes: int = MAX_BYTES) -> CompressResult:
    """Перекодирует mp3 в меньший битрейт на месте; оригинал переносится в originals/.

    Теги ID3 удаляются: в них бывает имя персонажа, а это спойлер.
    """
    size_before = path.stat().st_size
    kbps = pick_bitrate(await probe_duration(path), max_bytes)
    tmp = path.with_name(path.stem + ".tmp.mp3")
    await _run(
        "ffmpeg", "-y", "-v", "error", "-i", str(path),
        "-map", "0:a", "-map_metadata", "-1",
        "-c:a", "libmp3lame", "-b:a", f"{kbps}k",
        str(tmp),
    )  # fmt: skip
    if tmp.stat().st_size > max_bytes:
        tmp.unlink()
        raise CompressionError(f"После сжатия {path.name} всё ещё больше лимита")

    originals = path.parent / ORIGINALS_DIR
    originals.mkdir(exist_ok=True)
    shutil.move(path, originals / path.name)
    tmp.replace(path)
    result = CompressResult(path, kbps, size_before, path.stat().st_size)
    log.info(
        "audio_compressed",
        file=path.name,
        kbps=kbps,
        mb_before=round(size_before / 2**20, 1),
        mb_after=round(result.size_after / 2**20, 1),
    )
    return result


async def compress_oversized(audio_dir: Path, max_bytes: int = MAX_BYTES) -> int:
    """Сжимает все mp3 в каталоге, которые больше лимита. Возвращает число сжатых."""
    done = 0
    for path in sorted(audio_dir.glob("*.mp3")):
        if path.name.endswith(".tmp.mp3") or not needs_compression(path, max_bytes):
            continue
        try:
            await compress(path, max_bytes)
            done += 1
        except CompressionError:
            log.exception("audio_compress_failed", file=path.name)
    return done
