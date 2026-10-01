import pytest

from franky.domain.names import CharacterName, normalize


def test_normalize() -> None:
    assert normalize("  Пьер-Огюст   РЕНУАР!  ") == "пьер огюст ренуар"
    assert normalize("Ёжик") == "ежик"


def test_surname_first_name() -> None:
    name = CharacterName.parse("Маяковский, Владимир Владимирович")
    assert name.display == "Владимир Владимирович Маяковский"
    assert name.surname == "Маяковский"
    assert name.key == "маяковский владимир"
    assert set(name.all_aliases) >= {
        "Владимир Владимирович Маяковский",
        "Маяковский Владимир Владимирович",
        "Владимир Маяковский",
        "Маяковский",
    }


def test_version_is_stripped_and_shares_key() -> None:
    v2008 = CharacterName.parse("Болан, Марк вер.2008")
    plain = CharacterName.parse("Болан, Марк")
    assert v2008.version == "2008"
    assert v2008.key == plain.key
    assert v2008.display == "Марк Болан"


def test_parenthesised_real_name_becomes_alias() -> None:
    name = CharacterName.parse("Ошо (Раджниш, Чандра Мохан)")
    assert name.display == "Ошо"
    assert name.description is None
    assert "Чандра Мохан Раджниш" in name.all_aliases
    assert "Раджниш" in name.all_aliases


def test_parenthesised_description() -> None:
    name = CharacterName.parse("Enola Gay (самолет, сбросивший бомбу на Хиросиму)")
    assert name.display == "Enola Gay"
    assert name.description == "самолет, сбросивший бомбу на Хиросиму"
    assert name.all_aliases == ("Enola Gay",)


@pytest.mark.parametrize("title", ["Колобок", "Иов Многострадальный", "The Beatles"])
def test_name_without_comma(title: str) -> None:
    name = CharacterName.parse(title)
    assert name.display == title
    assert name.surname is None


def test_comma_before_version() -> None:
    name = CharacterName.parse("Бетховен, Людвиг ван, вер.2008")
    assert name.version == "2008"
    assert name.display == "Людвиг ван Бетховен"
    assert name.key == CharacterName.parse("Бетховен, Людвиг ван").key


def test_fuller_name_shares_key() -> None:
    assert (
        CharacterName.parse("Лири, Тимоти").key
        == CharacterName.parse("Лири, Тимоти Фрэнсис вер.2010").key
    )


def test_latin_homoglyphs_inside_russian_words() -> None:
    assert normalize("Беccи Смит") == normalize("Бесси Смит")  # «cc» здесь латинские
    assert normalize("The Beatles") == "the beatles"  # чисто латинские слова не трогаем
