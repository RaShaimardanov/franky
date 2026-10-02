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
    SendPhoto,
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
    PhotoSize,
    Update,
    User,
)
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from franky.bot import texts
from franky.bot.app import create_dispatcher
from franky.bot.callbacks import CatalogCb, FavCb, GameAct, GameCb
from franky.catalog.parser import ListingEntry
from franky.catalog.sync import upsert_entries
from franky.config import BotSettings, CatalogSettings, Settings
from franky.db.models import EpisodeKind
from franky.db.repositories import Repos

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
        if isinstance(method, SendMessage | SendAudio | SendPhoto):
            self._next_id += 1
            audio = photo = None
            markup = method.reply_markup
            if isinstance(method, SendAudio):
                audio = Audio(file_id=f"file-{self._next_id}", file_unique_id="u", duration=60)
            if isinstance(method, SendPhoto):
                photo = [PhotoSize(file_id="photo-1", file_unique_id="p", width=1, height=1)]
            return Message(  # type: ignore[return-value]
                message_id=self._next_id,
                date=datetime.now(UTC),
                chat=CHAT,
                text=getattr(method, "text", None),
                audio=audio,
                photo=photo,
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
    [welcome] = of(calls, SendPhoto)
    assert "«Фрэнки-шоу»" in (welcome.caption or "")
    assert len(welcome.caption or "") <= 1024  # лимит подписи к фото
    calls = await harness.text("/start")  # картинка повторно уходит по file_id
    assert of(calls, SendPhoto)[0].photo == "photo-1"

    calls = await harness.text(texts.BTN_PLAY)
    [audio] = of(calls, SendAudio)
    assert "Кто я сегодня?" in (audio.caption or "")
    assert audio.title == "Кто я?"  # метаданные не выдают ответ
    assert audio.performer == "Фрэнки-шоу"

    # Расшифровки нет — первая подсказка сразу год эфира.
    calls = await harness.press(GameCb(act=GameAct.HINT).pack())
    assert "2009" in of(calls, SendMessage)[0].text

    calls = await harness.text("Есенин")
    wrong = of(calls, SendMessage)[0].text
    assert "Есенин" in wrong
    assert "Осталось: 2 попытки" in wrong

    calls = await harness.text("<b>Есенин</b>")  # пользовательский текст экранируется
    assert "&lt;b&gt;" in of(calls, SendMessage)[0].text

    calls = await harness.text("маяковкий!")  # опечатка прощается
    reveal = of(calls, SendMessage)[0]
    assert "Шоу-тайм" in reveal.text
    assert "Владимир Владимирович Маяковский" in reveal.text

    # Второй раз файл уже не грузится — используется сохранённый file_id.
    await harness.text("/play")
    calls = await harness.press(GameCb(act=GameAct.SURRENDER).pack())
    assert "Сдаётесь" in of(calls, SendMessage)[0].text
    calls = await harness.text("/play")
    [audio] = of(calls, SendAudio)
    assert isinstance(audio.audio, str)
    assert audio.audio.startswith("file-")

    calls = await harness.text(texts.BTN_STATS)
    assert "Разгадано: 1" in of(calls, SendMessage)[0].text


async def test_favourite_toggle_updates_button(harness: Harness) -> None:
    await harness.text("/play")
    await harness.press(GameCb(act=GameAct.SURRENDER).pack())

    origin_markup = FavCb(episode_id=1).pack()
    calls = await harness.press(origin_markup)
    assert of(calls, AnswerCallbackQuery)[0].text == texts.FAV_ADDED

    calls = await harness.text(texts.BTN_FAVOURITES)
    assert "коллекция ролей</b> (1)" in of(calls, SendMessage)[0].text


async def test_search_inline_and_text(harness: Harness) -> None:
    calls = await harness.inline("маяк")
    [answer] = of(calls, AnswerInlineQuery)
    assert [r.title for r in answer.results] == ["Владимир Владимирович Маяковский"]

    calls = await harness.text("маяк")  # вне игры текст — это поиск по архиву
    [found] = of(calls, SendMessage)
    assert found.reply_markup.inline_keyboard[0][0].text == "Владимир Владимирович Маяковский"

    calls = await harness.text("абракадабра")
    assert "Такой роли в моей коллекции нет" in of(calls, SendMessage)[0].text


async def test_unknown_callback_does_not_crash(harness: Harness) -> None:
    calls = await harness.press(GameCb(act=GameAct.HINT).pack())
    [answer] = of(calls, AnswerCallbackQuery)
    assert answer.show_alert
    assert of(calls, EditMessageReplyMarkup) == []


async def test_catalog_browse_and_search(harness: Harness) -> None:
    calls = await harness.text(texts.BTN_CATALOG)
    [index] = of(calls, SendMessage)
    assert "1 роль, 1 выпуск" in index.text
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
    assert "Ролей послушано: 0" in of(calls, SendMessage)[0].text  # загадка всё ещё идёт


async def test_quote_hint_and_content_search(harness: Harness, session: AsyncSession) -> None:
    quote = "Недаром же я родился летом, шутили мои родители, глядя на рыжего сына."
    text = f"В этом выпуске про джинна и лампу. {quote}"
    await Repos(session).transcripts.upsert(1, text, [quote])
    await session.commit()

    await harness.text("/play")
    calls = await harness.press(GameCb(act=GameAct.HINT).pack())
    assert quote in of(calls, SendMessage)[0].text  # первая подсказка — цитата
    calls = await harness.press(GameCb(act=GameAct.HINT).pack())
    assert "2009" in of(calls, SendMessage)[0].text  # затем год

    # Поиск по содержанию: в каталоге (inline) и обычным текстом вне игры.
    calls = await harness.inline("каталог: джинн")
    [answer] = of(calls, AnswerInlineQuery)
    content = [r for r in answer.results if r.id.startswith("t")]
    assert content
    assert "джинна" in content[0].description
    assert content[0].input_message_content.message_text == "📚 Владимир Владимирович Маяковский"

    await harness.press(GameCb(act=GameAct.SURRENDER).pack())
    calls = await harness.text("лампа")
    [found] = of(calls, SendMessage)
    assert found.text == texts.CONTENT_RESULTS
