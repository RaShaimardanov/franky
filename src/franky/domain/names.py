"""Разбор названий выпусков с fshow.info и нормализация имён персонажей.

Примеры заголовков на сайте:
    «Маяковский, Владимир Владимирович»
    «Болан, Марк вер.2008»                       — повторный выпуск о том же персонаже
    «Ошо (Раджниш, Чандра Мохан)»                — в скобках настоящее имя
    «Enola Gay (самолет, сбросивший бомбу ...)»  — в скобках пояснение
    «Колобок»
"""

import re
from dataclasses import dataclass, field

_VERSION_RE = re.compile(r"[\s,]+вер\.?\s*(?P<version>\d{4})\s*$", re.IGNORECASE)
_PARENS_RE = re.compile(r"^(?P<base>.*?)\s*\((?P<note>[^()]+)\)\s*$")
_NON_WORD_RE = re.compile(r"[^\w]+")
_CYRILLIC_RE = re.compile(r"[а-яё]")
# Латинские буквы, которые на сайте иногда попадаются внутри русских слов («Беccи»).
_HOMOGLYPHS = str.maketrans("aceopxyk", "асеорхук")


def normalize(text: str) -> str:
    """Приводит строку к виду для сравнения: нижний регистр, ё→е, без пунктуации."""
    text = text.lower().replace("ё", "е")
    words = _NON_WORD_RE.sub(" ", text).split()
    return " ".join(w.translate(_HOMOGLYPHS) if _CYRILLIC_RE.search(w) else w for w in words)


@dataclass(frozen=True, slots=True)
class PersonName:
    """Имя в формате сайта «Фамилия, Имя Отчество» или просто «Имя»."""

    display: str  # «Владимир Владимирович Маяковский»
    surname: str | None  # «Маяковский», если имя было с запятой
    aliases: tuple[str, ...]

    @classmethod
    def parse(cls, raw: str) -> "PersonName":
        raw = " ".join(raw.split())
        if "," not in raw:
            return cls(display=raw, surname=None, aliases=(raw,))

        surname, _, given = (part.strip() for part in raw.partition(","))
        display = f"{given} {surname}".strip()
        aliases = [display, f"{surname} {given}".strip(), surname]
        first_name = given.split()[0] if given else ""
        if first_name and len(given.split()) > 1:
            aliases.append(f"{first_name} {surname}")
        return cls(display=display, surname=surname, aliases=tuple(dict.fromkeys(aliases)))


@dataclass(frozen=True, slots=True)
class CharacterName:
    key: str  # нормализованный ключ, общий для всех версий выпуска
    display: str
    surname: str | None
    aliases: tuple[str, ...]
    description: str | None = None
    version: str | None = None
    extra_aliases: tuple[str, ...] = field(default=())

    @property
    def all_aliases(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys((*self.aliases, *self.extra_aliases)))

    @classmethod
    def parse(cls, title: str) -> "CharacterName":
        title = " ".join(title.split())

        version = None
        if match := _VERSION_RE.search(title):
            version = match["version"]
            title = title[: match.start()]

        description = None
        extra: tuple[str, ...] = ()
        if match := _PARENS_RE.match(title):
            title, note = match["base"], match["note"].strip()
            if _looks_like_name(note):
                extra = PersonName.parse(note).aliases
            else:
                description = note

        person = PersonName.parse(title)
        return cls(
            key=_character_key(title),
            display=person.display,
            surname=person.surname,
            aliases=person.aliases,
            description=description,
            version=version,
            extra_aliases=extra,
        )


def _character_key(title: str) -> str:
    """Общий ключ для разных записей об одном человеке: фамилия + первое имя.

    «Лири, Тимоти» и «Лири, Тимоти Фрэнсис» → «лири тимоти».
    """
    surname, comma, given = title.partition(",")
    if not comma:
        return normalize(title)
    first = normalize(given).split()[:1]
    return " ".join([normalize(surname), *first])


def _looks_like_name(text: str) -> bool:
    """«Раджниш, Чандра Мохан» — имя; «самолет, сбросивший бомбу» — пояснение."""
    words = [w for w in re.split(r"[\s,]+", text) if w]
    return bool(words) and all(w[0].isupper() for w in words)
