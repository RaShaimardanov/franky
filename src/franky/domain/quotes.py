"""Отбор цитат из расшифровки выпуска для подсказок.

Цитата не должна выдавать ответ, поэтому отбрасываются:
- начало (заставка, приветствия) и конец эфира (там ведущий объявляет ответ);
- фразы с именем персонажа в любой форме («Маяковского», «Маяковским»);
- реплики звонящих и разговоры о версиях — слушатели могли назвать верный ответ;
- галлюцинации распознавания речи («Субтитры сделал …»).
"""

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from franky.domain.names import normalize

SKIP_START_SECONDS = 240
SKIP_END_SHARE = 0.25
MIN_CHARS, MAX_CHARS = 60, 220
MIN_WORDS = 8
MAX_QUOTES = 8

_SENTENCE_RE = re.compile(r"(?<=[.!?…])\s+")
# Корни слов, по которым видно, что фраза — о самой игре, а не о герое выпуска.
_GAME_TALK = (
    "верси", "роли", "роль", "угада", "отгада", "фрэнк", "френк", "шоу", "приз", "диск",
    "звон", "алло", "автоответ", "меня зовут", "здравств", "привет", "серебрян", "silver",
    "эфир", "маэстро", "загадк", "дорогие мои", "дамы и господа", "приемник", "слабонерв",
    "новую историю", "новую жизнь", "развлечени",
)  # fmt: skip
_HALLUCINATIONS = ("субтитр", "редактор", "продолжение следует", "dimatorzok", "корректор")


@dataclass(frozen=True, slots=True)
class Segment:
    start: float
    text: str


def forbidden_stems(names: Iterable[str]) -> set[str]:
    """Основы слов имени: «Маяковский» → «маяков», чтобы ловить любые падежи."""
    stems = set()
    for name in names:
        for word in normalize(name).split():
            if len(word) >= 3:
                stems.add(word[: max(4, len(word) - 2)] if len(word) > 5 else word)
    return stems


def _is_clean(sentence: str, stems: set[str]) -> bool:
    if not MIN_CHARS <= len(sentence) <= MAX_CHARS or len(sentence.split()) < MIN_WORDS:
        return False
    lower = sentence.lower().replace("ё", "е")
    if any(marker in lower for marker in (*_GAME_TALK, *_HALLUCINATIONS)):
        return False
    words = normalize(sentence).split()
    return not any(word.startswith(stem) for word in words for stem in stems)


def extract_quotes(segments: Sequence[Segment], duration: float, names: Iterable[str]) -> list[str]:
    """До MAX_QUOTES фраз, равномерно взятых из «тела» выпуска."""
    stems = forbidden_stems(names)
    window_end = duration * (1 - SKIP_END_SHARE)
    candidates: list[str] = []
    for segment in segments:
        if not SKIP_START_SECONDS <= segment.start <= window_end:
            continue
        for sentence in _SENTENCE_RE.split(segment.text.strip()):
            sentence = sentence.strip(" -–—")
            if _is_clean(sentence, stems) and sentence not in candidates:
                candidates.append(sentence)

    # Самые «биографичные» фразы — с числами и именами собственными; порядок — как в эфире.
    best = sorted(candidates, key=_informativeness, reverse=True)[:MAX_QUOTES]
    return [c for c in candidates if c in best]


_FIRST_PERSON = frozenset(
    ["я", "мой", "моя", "мое", "мои", "меня", "мне", "мной", "моих", "моей", "моего", "моим", "мою"]
)


def _informativeness(sentence: str) -> float:
    """Ведущий рассказывает о герое от первого лица — такие фразы и есть биография.
    Вставки-факты («каждые 6 секунд в мире…») в третьем лице получают меньше очков."""
    words = sentence.split()
    first_person = any(w in _FIRST_PERSON for w in normalize(sentence).split())
    digits = sum(any(ch.isdigit() for ch in w) for w in words)
    proper = sum(w[:1].isupper() for w in words[1:])
    return 4 * first_person + min(digits, 2) + 0.5 * min(proper, 3) + min(len(sentence), 160) / 160
