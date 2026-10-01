import pytest

from franky.domain.guess import is_correct_guess
from franky.domain.names import CharacterName


def check(title: str, guess: str) -> bool:
    name = CharacterName.parse(title)
    return is_correct_guess(guess, name.all_aliases, name.surname)


@pytest.mark.parametrize(
    "guess",
    [
        "Маяковский",
        "маяковский",
        "Маяковкий",  # опечатка
        "Владимир Маяковский",
        "Маяковский Владимир",
        "В. Маяковский",
        "Владимир Владимирович Маяковский",
        "  МАЯКОВСКИЙ!!! ",
    ],
)
def test_accepts_reasonable_answers(guess: str) -> None:
    assert check("Маяковский, Владимир Владимирович", guess)


@pytest.mark.parametrize(
    "guess",
    ["Владимир", "Есенин", "Сергей Маяковский", "", "   ", "Маяк"],
)
def test_rejects_wrong_answers(guess: str) -> None:
    assert not check("Маяковский, Владимир Владимирович", guess)


def test_yo_and_e_are_equal() -> None:
    assert check("Шнитке, Альфред", "Альфред Шнитке")
    assert check("Королёв, Сергей Павлович", "Королев")


def test_real_name_alias() -> None:
    assert check("Ошо (Раджниш, Чандра Мохан)", "Ошо")
    assert check("Ошо (Раджниш, Чандра Мохан)", "Раджниш")


def test_name_without_surname_needs_full_match() -> None:
    assert check("Колобок", "колобок")
    assert check("Колобок", "Калобок")
    assert check("The Beatles", "the beatles")
    assert not check("The Beatles", "Rolling Stones")
