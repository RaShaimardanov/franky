"""Проверка ответа слушателя: прощает опечатки, регистр, ё/е и порядок слов."""

from collections.abc import Iterable

from rapidfuzz import fuzz

from franky.domain.names import normalize

# Насколько слово ответа может отличаться от правильного (0–100).
WORD_SIMILARITY = 80
WHOLE_SIMILARITY = 85
MIN_FUZZY_LENGTH = 4


def _word_matches(guess_word: str, answer_word: str) -> bool:
    if guess_word == answer_word:
        return True
    if len(guess_word) == 1:  # инициал: «в маяковский»
        return answer_word.startswith(guess_word)
    if min(len(guess_word), len(answer_word)) < MIN_FUZZY_LENGTH:
        return False
    return fuzz.ratio(guess_word, answer_word) >= WORD_SIMILARITY


def is_correct_guess(guess: str, aliases: Iterable[str], surname: str | None) -> bool:
    """Засчитывает ответ, если он совпадает с одним из вариантов имени.

    Для имён вида «Фамилия, Имя» достаточно фамилии, но ответ обязан её содержать:
    «Маяковский», «Маяковкий» и «В. Маяковский» засчитаются, а просто «Владимир» — нет.
    """
    norm_guess = normalize(guess)
    if not norm_guess:
        return False
    guess_words = norm_guess.split()

    for alias in aliases:
        norm_alias = normalize(alias)
        if norm_guess == norm_alias:
            return True
        if (
            len(norm_guess) >= MIN_FUZZY_LENGTH
            and fuzz.ratio(norm_guess, norm_alias) >= WHOLE_SIMILARITY
        ):
            return True

    if surname is None:
        return False

    surname_words = normalize(surname).split()
    if not all(any(_word_matches(g, s) for g in guess_words) for s in surname_words):
        return False

    # Остальные слова ответа должны встречаться в каком-нибудь полном варианте имени.
    full_words = {w for alias in aliases for w in normalize(alias).split()}
    return all(any(_word_matches(g, w) for w in full_words) for g in guess_words)
