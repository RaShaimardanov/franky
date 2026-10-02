"""Сквозные тесты бота: настоящие диспетчер, хендлеры и Postgres, поддельный Bot API."""

from collections.abc import AsyncGenerator
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pytest
from aiogram import Bot
from aiogram.client.session.base import BaseSession
from aiogram.methods import (
    AnswerCallbackQuery,
    AnswerInlineQuery,
    EditMessageReplyMarkup,
    EditMessageText,
    SendAudio,
    SendMessage,
    TelegramMethod,
)
from aiogram.methods.base import TelegramType
from aiogram.types import (
    Audio,
    CallbackQuery,
    Chat,
    InlineKeyboardMarkup,
    InlineQuery,
    Message,
    Update,
    User,
)
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from franky.bot.app import create_dispatcher
from franky.bot.callbacks import CatalogCb, FavCb, GameAct, GameCb
from franky.catalog.parser import ListingEntry
from franky.catalog.sync import upsert_entries
from franky.config import BotSettings, CatalogSettings, Settings
from franky.db.models import EpisodeKind

USER = User(id=777, is_bot=False, first_name="Тестер", language_code="ru")
CHAT = Chat(id=USER.id, type="private")


class FakeSession(BaseSession):
    """Запоминает вызовы Bot API и отвечает правдоподобными объектами."""

    def __init__(self) -> None:
        super().__init__()
        self.calls: list[TelegramMethod[Any]] = []
        self._next_id = 100

    async def make_request(
        self,
        bot: Bot,
        method: TelegramMethod[TelegramType],
        timeout: int | None = None,  # noqa: ASYNC109 — сигнатура задана BaseSession
    ) -> TelegramType:
        self.calls.append(method)
        if isinstance(method, SendMessage | SendAudio):
            self._next_id += 1
            audio = None
            markup = method.reply_markup
            if isinstance(method, SendAudio):
                audio = Audio(file_id=f"file-{self._next_id}", file_unique_id="u", duration=60)
            return Message(  # type: ignore[return-value]
                message_id=self._next_id,
                date=datetime.now(UTC),
                chat=CHAT,
                text=getattr(method, "text", None),
                audio=audio,
                reply_markup=markup if isinstance(markup, InlineKeyboardMarkup) else None,
            )
        return True  # type: ignore[return-value]

    async def close(self) -> None:
        pass

    async def stream_content(  # type: ignore[override]
        self, *args: Any, **kwargs: Any
    ) -> AsyncGenerator[bytes, None]:
        yield b""

    def take(self) -> list[TelegramMethod[Any]]:
        calls, self.calls = self.calls, []
        return calls


class Harness:
    def __init__(self, bot: Bot, session: FakeSession, dp: Any) -> None:
        self.bot, self.api, self.dp = bot, session, dp
        self._update_id = 0
        self.last_audio_message: Message | None = None

    async def _feed(self, **kwargs: Any) -> list[TelegramMethod[Any]]:
        self._update_id += 1
        await self.dp.feed_update(self.bot, Update(update_id=self._update_id, **kwargs))
        return self.api.take()

    async def text(self, text: str) -> list[TelegramMethod[Any]]:
        message = Message(
            message_id=self._update_id + 1,
            date=datetime.now(UTC),
            chat=CHAT,
            from_user=USER,
            text=text,
        )
        return await self._feed(message=message)

    async def press(self, data: str) -> list[TelegramMethod[Any]]:
        origin = Message(message_id=1, date=datetime.now(UTC), chat=CHAT, text="…")
        callback = CallbackQuery(
            id=str(self._update_id), from_user=USER, chat_instance="ci", data=data, message=origin
        )
        return await self._feed(callback_query=callback)

    async def inline(self, query: str) -> list[TelegramMethod[Any]]:
        inline = InlineQuery(id="iq", from_user=USER, query=query, offset="")
        return await self._feed(inline_query=inline)


@pytest.fixture
async def harness(session: AsyncSession, tmp_path: Path) -> Harness:
    entries = [
        ListingEntry(
            1, "Маяковский, Владимир Владимирович", EpisodeKind.REGULAR, date(2009, 8, 9), 2009
        ),
    ]
    (tmp_path / "1.mp3").write_bytes(b"ID3")
    await upsert_entries(session, entries, tmp_path)
    await session.commit()

    settings = Settings(
        bot=BotSettings(token="42:TEST"),  # type: ignore[arg-type]
        catalog=CatalogSettings(audio_dir=tmp_path),
    )
    fake = FakeSession()
    bot = Bot("42:TEST", session=fake)
    factory = async_sessionmaker(session.bind, expire_on_commit=False)
    dp = create_dispatcher(settings, factory, bot)
    return Harness(bot, fake, dp)


def of(calls: list[TelegramMethod[Any]], kind: type[Any]) -> list[Any]:
    return [c for c in calls if isinstance(c, kind)]


async def test_full_game_round(harness: Harness) -> None:
    calls = await harness.text("/start")
    assert "Фрэнки-шоу" in of(calls, SendMessage)[0].text

    calls = await harness.text("/play")
    [audio] = of(calls, SendAudio)
    assert "Кто это?" in (audio.caption or "")
    assert audio.title == "Кто я?"  # метаданные не выдают ответ
    assert audio.performer == "Фрэнки-шоу"

    calls = await harness.press(GameCb(act=GameAct.HINT).pack())
    assert "2009" in of(calls, SendMessage)[0].text

    calls = await harness.text("Есенин")
    assert "Нет, это не Есенин" in of(calls, SendMessage)[0].text

    calls = await harness.text("<b>Есенин</b>")  # пользовательский текст экранируется
    assert "&lt;b&gt;" in of(calls, SendMessage)[0].text

    calls = await harness.text("маяковкий!")  # опечатка прощается
    reveal = of(calls, SendMessage)[0]
    assert "Верно" in reveal.text
    assert "Владимир Владимирович Маяковский" in reveal.text

    # Второй раз файл уже не грузится — используется сохранённый file_id.
    await harness.text("/play")
    calls = await harness.press(GameCb(act=GameAct.SURRENDER).pack())
    assert "Ответ" in of(calls, SendMessage)[0].text
    calls = await harness.text("/play")
    [audio] = of(calls, SendAudio)
    assert isinstance(audio.audio, str)
    assert audio.audio.startswith("file-")

    calls = await harness.text("/stats")
    assert "Угадано: 1" in of(calls, SendMessage)[0].text


async def test_favourite_toggle_updates_button(harness: Harness) -> None:
    await harness.text("/play")
    await harness.press(GameCb(act=GameAct.SURRENDER).pack())

    origin_markup = FavCb(episode_id=1).pack()
    calls = await harness.press(origin_markup)
    assert of(calls, AnswerCallbackQuery)[0].text == "Добавлено в избранное ⭐"

    calls = await harness.text("/favourites")
    assert "Избранное</b> (1)" in of(calls, SendMessage)[0].text


async def test_search_inline_and_text(harness: Harness) -> None:
    calls = await harness.inline("маяк")
    [answer] = of(calls, AnswerInlineQuery)
    assert [r.title for r in answer.results] == ["Владимир Владимирович Маяковский"]

    calls = await harness.text("маяк")  # вне игры текст — это поиск по архиву
    [found] = of(calls, SendMessage)
    assert found.reply_markup.inline_keyboard[0][0].text == "Владимир Владимирович Маяковский"

    calls = await harness.text("абракадабра")
    assert "Никого не нашлось" in of(calls, SendMessage)[0].text


async def test_unknown_callback_does_not_crash(harness: Harness) -> None:
    calls = await harness.press(GameCb(act=GameAct.HINT).pack())
    [answer] = of(calls, AnswerCallbackQuery)
    assert answer.show_alert
    assert of(calls, EditMessageReplyMarkup) == []


async def test_catalog_browse_and_search(harness: Harness) -> None:
    calls = await harness.text("📚 Каталог")
    [index] = of(calls, SendMessage)
    assert "1 персонаж, 1 выпуск" in index.text
    buttons = [b for row in index.reply_markup.inline_keyboard for b in row]
    assert [b.text for b in buttons][:1] == ["М"]

    calls = await harness.press(CatalogCb(letter="М").pack())
    [page] = of(calls, EditMessageText)
    first = page.reply_markup.inline_keyboard[0][0]
    assert first.text == "Маяковский Владимир Владимирович"

    calls = await harness.inline("каталог: маяк")
    [answer] = of(calls, AnswerInlineQuery)
    assert answer.results[0].input_message_content.message_text == (
        "📚 Владимир Владимирович Маяковский"
    )


async def test_catalog_pick_during_game_is_not_a_guess(harness: Harness) -> None:
    await harness.text("/play")
    calls = await harness.text("📚 Владимир Владимирович Маяковский")
    [card] = of(calls, SendMessage)
    assert "Выпусков в архиве: 1" in card.text  # карточка, а не «Верно!»

    calls = await harness.text("/stats")
    assert "Загадок: 0" in of(calls, SendMessage)[0].text  # загадка всё ещё не решена
