"""Алфавитный указатель каталога: персонажи сортируются и группируются по фамилии."""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Protocol

from franky.domain.names import normalize

LATIN_GROUP = "A–Z"
OTHER_GROUP = "#"


class Named(Protocol):
    @property
    def name(self) -> str: ...
    @property
    def surname(self) -> str | None: ...


def index_name(name: str, surname: str | None) -> str:
    """Как имя стоит в указателе: «Маяковский Владимир Владимирович», «Колобок»."""
    if not surname or not name.endswith(surname):
        return name
    given = name[: -len(surname)].strip()
    return f"{surname} {given}".strip()


def index_letter(text: str) -> str:
    """Буква раздела указателя. Ё живёт в Е, все латинские имена — в одном разделе A–Z."""
    for ch in text:
        if not ch.isalpha():
            continue
        upper = ch.upper()
        if "А" <= upper <= "Я" or upper == "Ё":
            return "Е" if upper == "Ё" else upper
        if "A" <= upper <= "Z":
            return LATIN_GROUP
        return OTHER_GROUP
    return OTHER_GROUP


def _letter_order(letter: str) -> tuple[int, str]:
    rank = {LATIN_GROUP: 1, OTHER_GROUP: 2}.get(letter, 0)
    return rank, letter


@dataclass(frozen=True, slots=True)
class IndexEntry[T]:
    item: T
    title: str  # подпись в указателе
    letter: str


def build_index[T: Named](items: Iterable[T]) -> dict[str, list[IndexEntry[T]]]:
    """Разделы указателя в алфавитном порядке (кириллица, затем A–Z, затем прочее)."""
    entries = []
    for item in items:
        title = index_name(item.name, item.surname)
        entries.append(IndexEntry(item, title, index_letter(title)))
    entries.sort(key=lambda e: (_letter_order(e.letter), normalize(e.title)))

    index: dict[str, list[IndexEntry[T]]] = {}
    for entry in entries:
        index.setdefault(entry.letter, []).append(entry)
    return dict(sorted(index.items(), key=lambda kv: _letter_order(kv[0])))


def paginate[T](items: Sequence[T], page: int, per_page: int) -> tuple[Sequence[T], int, int]:
    """Срез страницы, номер страницы (с поправкой на границы) и число страниц."""
    pages = max(1, -(-len(items) // per_page))
    page = min(max(page, 0), pages - 1)
    return items[page * per_page : (page + 1) * per_page], page, pages
