"""HTTP-клиент к архиву fshow.info. Сайт старый, поэтому ходим вежливо и по одному."""

import asyncio
from pathlib import Path
from types import TracebackType
from typing import Self

import httpx
import structlog

from franky.catalog.parser import ListingEntry, parse_download_code, parse_listing

log = structlog.get_logger(__name__)

SITE_ENCODING = "cp1251"
USER_AGENT = "FrankyShowBot/2.0 (+archive mirror for a Telegram quiz bot)"


class CatalogError(Exception):
    pass


class FshowClient:
    def __init__(self, base_url: str, *, request_delay: float = 2.0) -> None:
        self._delay = request_delay
        self._http = httpx.AsyncClient(
            base_url=base_url,
            headers={"User-Agent": USER_AGENT},
            timeout=httpx.Timeout(30.0, read=300.0),
            follow_redirects=True,
        )

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self._http.aclose()

    async def fetch_listing(self) -> list[ListingEntry]:
        # Кнопка «Показать роли» — это POST формы со списком.
        response = await self._http.post(
            "index.php?all", data={"show": "Показать роли".encode(SITE_ENCODING)}
        )
        response.raise_for_status()
        entries = parse_listing(response.content.decode(SITE_ENCODING, errors="replace"))
        if not entries:
            raise CatalogError(
                "На странице не найдено ни одного выпуска — разметка сайта изменилась?"
            )
        return entries

    async def download(self, site_id: int, target: Path) -> None:
        """Скачивает mp3 выпуска в target (атомарно, через временный файл)."""
        page = await self._http.get(f"fc/out.php?{site_id}")
        page.raise_for_status()
        code = parse_download_code(page.content.decode(SITE_ENCODING, errors="replace"))
        if code is None:
            raise CatalogError(f"Не найден код подтверждения на странице выпуска {site_id}")

        await asyncio.sleep(self._delay)
        tmp = target.with_suffix(target.suffix + ".part")
        target.parent.mkdir(parents=True, exist_ok=True)
        async with self._http.stream(
            "POST", "fc/download.php", data={"code": code, "add": "Download"}
        ) as response:
            response.raise_for_status()
            content_type = response.headers.get("content-type", "")
            if "text/html" in content_type:
                raise CatalogError(f"Сайт вернул HTML вместо аудио для выпуска {site_id}")
            size = 0
            with tmp.open("wb") as fh:
                async for chunk in response.aiter_bytes(1 << 16):
                    fh.write(chunk)
                    size += len(chunk)
        tmp.replace(target)
        log.info("episode_downloaded", site_id=site_id, size=size)
        await asyncio.sleep(self._delay)
