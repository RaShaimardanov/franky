from dataclasses import dataclass

from franky.domain.catalog import LATIN_GROUP, build_index, index_letter, index_name, paginate


@dataclass
class Item:
    name: str
    surname: str | None = None


def test_index_name_puts_surname_first() -> None:
    assert index_name("Владимир Владимирович Маяковский", "Маяковский") == (
        "Маяковский Владимир Владимирович"
    )
    assert index_name("Колобок", None) == "Колобок"


def test_index_letter() -> None:
    assert index_letter("Маяковский") == "М"
    assert index_letter("Ёжик в тумане") == "Е"
    assert index_letter("The Beatles") == LATIN_GROUP
    assert index_letter("«Шоу»") == "Ш"


def test_build_index_orders_sections_and_entries() -> None:
    index = build_index(
        [
            Item("The Who"),
            Item("Владимир Маяковский", "Маяковский"),
            Item("Марк Болан", "Болан"),
            Item("Мэрилин Монро", "Монро"),
            Item("Ёжик в тумане"),
        ]
    )
    assert list(index) == ["Б", "Е", "М", LATIN_GROUP]
    assert [e.title for e in index["М"]] == ["Маяковский Владимир", "Монро Мэрилин"]
    assert index["Б"][0].title == "Болан Марк"


def test_paginate_clamps_page() -> None:
    items = list(range(25))
    assert paginate(items, 0, 10) == (list(range(10)), 0, 3)
    assert paginate(items, 2, 10) == ([20, 21, 22, 23, 24], 2, 3)
    assert paginate(items, 99, 10)[1] == 2
    assert paginate([], 0, 10) == ([], 0, 1)
