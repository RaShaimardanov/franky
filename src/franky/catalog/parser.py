"""Разбор HTML-страниц fshow.info."""

import re
from dataclasses import dataclass
from datetime import date, datetime

from bs4 import BeautifulSoup

from franky.db.models import EpisodeKind

_OUT_LINK_RE = re.compile(r"out\.php\?(?P<id>-?\d+)")
# «07.02.10  Enola Gay (...)», «=2006=  The Who», «06.09.09 (ПРАЗДНИК) Презентация книги»
_TITLE_RE = re.compile(
    r"^(?P<when>\d{2}\.\d{2}\.\d{2}|=\d{4}=)\s+(?:\((?P<kind>[^)]+)\)\s+)?(?P<title>.+)$"
)
_KINDS = {"ПРАЗДНИК": EpisodeKind.SPECIAL, "ФРАГМЕНТ": EpisodeKind.FRAGMENT}


@dataclass(frozen=True, slots=True)
class ListingEntry:
    site_id: int
    title: str
    kind: EpisodeKind
    aired_on: date | None
    aired_year: int | None


def parse_listing(html: str) -> list[ListingEntry]:
    """Список выпусков со страницы «все» в режиме «Показать роли»."""
    soup = BeautifulSoup(html, "html.parser")
    container = soup.find(id="list") or soup
    entries: list[ListingEntry] = []
    for link in container.find_all("a", href=_OUT_LINK_RE):
        id_match = _OUT_LINK_RE.search(str(link.get("href", "")))
        text = " ".join(link.get_text(" ").replace("\xa0", " ").split())
        title_match = _TITLE_RE.match(text)
        if not id_match or not title_match:
            continue
        aired_on, aired_year = _parse_when(title_match["when"])
        kind_label = (title_match["kind"] or "").strip().upper()
        entries.append(
            ListingEntry(
                site_id=int(id_match["id"]),
                title=title_match["title"].strip(),
                kind=_KINDS.get(kind_label, EpisodeKind.REGULAR),
                aired_on=aired_on,
                aired_year=aired_year,
            )
        )
    return entries


def parse_download_code(html: str) -> str | None:
    """Код подтверждения со страницы скачивания (он показан на ней же в <span id="nekto">)."""
    node = BeautifulSoup(html, "html.parser").find(id="nekto")
    code = node.get_text(strip=True) if node else ""
    return code or None


def _parse_when(token: str) -> tuple[date | None, int | None]:
    if token.startswith("="):
        return None, int(token.strip("="))
    parsed = datetime.strptime(token, "%d.%m.%y").date()
    return parsed, parsed.year
