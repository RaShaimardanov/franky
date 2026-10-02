from franky.domain.names import CharacterName
from franky.domain.quotes import Segment, extract_quotes, forbidden_stems

NAME = CharacterName.parse("Миронов, Андрей Александрович")
BIO = "Так, начиная примерно с 72-го года, меня начинает носить на руках вся страна."


def quotes(*segments: tuple[float, str], duration: float = 3000) -> list[str]:
    return extract_quotes([Segment(s, t) for s, t in segments], duration, NAME.all_aliases)


def test_takes_biography_from_the_body_of_the_show() -> None:
    assert quotes((600, BIO)) == [BIO]


def test_skips_intro_and_finale() -> None:
    assert quotes((30, BIO)) == []  # заставка и приветствия
    assert quotes((2900, BIO)) == []  # в конце эфира объявляют ответ


def test_name_in_any_case_form_is_never_quoted() -> None:
    leak = "И вот уже вся страна обсуждает Миронова, его роли в кино и его остроумие на сцене."
    assert quotes((600, leak)) == []
    assert "мирон" in forbidden_stems(NAME.all_aliases)  # ловит «Миронова», «Мироновым»


def test_skips_callers_and_game_talk() -> None:
    caller = "Алло, здравствуйте, меня зовут Ира, мне кажется, сегодня вы великий актёр театра."
    version = "Прекрасная версия, но уверяю вас, всё ещё гораздо более запущено, дорогие мои."
    assert quotes((600, caller), (700, version)) == []


def test_skips_whisper_hallucinations_and_short_lines() -> None:
    assert (
        quotes((600, "Субтитры сделал DimaTorzok для всех зрителей этого прекрасного эфира.")) == []
    )
    assert quotes((600, "Да, я помню.")) == []


def test_prefers_first_person_over_trivia() -> None:
    many = [
        (
            600 + i,
            f"По данным статистики за {2000 + i} год, каждые 6 секунд в мире умирает курильщик.",
        )
        for i in range(12)
    ]
    result = quotes((590, BIO), *many)
    assert BIO in result
    assert len(result) == 8
