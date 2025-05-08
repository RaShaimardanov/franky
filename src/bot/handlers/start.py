import os
from typing import Any, Optional, Union

from aiogram import Router, F
from aiogram.enums import ChatAction
from aiogram.exceptions import TelegramBadRequest, TelegramNetworkError
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    Message,
    FSInputFile,
    MessageReactionUpdated,
    InputMediaAudio,
    CallbackQuery,
    ReactionTypeEmoji,
)
from aiogram.utils.chat_action import ChatActionSender
from fluentogram import TranslatorRunner

from src.bot.keyboards.user import user_setting_kb
from src.bot.utils.callback_data import UserSettingsCallback
from src.bot.utils.send_message import notify_admin
from src.bot.utils.states import StateUserActions
from src.core.constants import DEFAULT_AUDIO_TITLE, DEFAULT_AUDIO_PERFORMER
from src.core.exceptions import AudioServiceException
from src.core.logger import logger
from src.core.paths import BROADCASTS_DIR
from src.database.models.broadcast import Broadcast
from src.database.models.user import User
from src.database.repo.requests import RequestsRepo
from src.services.audio import AudioService

router = Router()


@router.message(CommandStart())
async def command_start_handler(
    message: Message,
    repo: RequestsRepo,
    i18n: TranslatorRunner,
) -> None:

    await message.answer(text=i18n.cmd.start())


@router.message(Command("show"))
async def command_show_handler(
    message: Message,
    state: FSMContext,
    repo: RequestsRepo,
    user: User,
    i18n: TranslatorRunner,
) -> None:
    """
    Хендлер обработки команды '/show'
    Отправляет пользователю аудиофайл с выпуском
    """
    while True:
        broadcast = await repo.broadcasts.get_random_broadcast()
        service = AudioService(user, broadcast, repo, message.bot)
        if not broadcast:
            await message.answer(i18n.info.no_broadcasts())
            logger.info("Запрос случайного выпуска. База данных пуста")
            return
        print(broadcast.id)
        try:
            async with ChatActionSender.upload_voice(
                chat_id=message.chat.id, bot=message.bot
            ):

                result = await service.send_audio()
                if result:
                    if not user.show_role_name:
                        await state.update_data(broadcast=broadcast)
                        await state.set_state(StateUserActions.listen)
                    break
        except Exception as e:
            logger.error(f"Failed to send audio: {str(e)}")
            continue


@router.message(Command("test"))
async def command_test_handler(
    message: Message,
    repo: RequestsRepo,
    user: User,
    i18n: TranslatorRunner,
):

    pass


@router.message(Command("settings"))
async def command_settings_handler(
    message: Message,
    user: User,
    i18n: TranslatorRunner,
) -> None:
    await message.answer(
        text=i18n.cmd.settings(), reply_markup=user_setting_kb(user.show_role_name)
    )


@router.callback_query(UserSettingsCallback.filter())
async def edit_settings_callback(
    callback: CallbackQuery,
    callback_data: UserSettingsCallback,
    repo: RequestsRepo,
    user: User,
    i18n: TranslatorRunner,
) -> None:
    await repo.users.update(
        user, update_data={"show_role_name": callback_data.show_role_name}
    )
    await callback.answer(text=i18n.settings.saved(), show_alert=True)
    await callback.message.delete()


@router.callback_query(F.data == "back")
async def back_callback(
    callback: CallbackQuery,
    repo: RequestsRepo,
    user: User,
) -> None:
    await callback.message.delete()


@router.message(F.text, StateUserActions.listen)
async def wait_version_message(
    message: Message,
    state: FSMContext,
    repo: RequestsRepo,
    user: User,
    i18n: TranslatorRunner,
):
    broadcast = await state.get_value("broadcast")
    if message.text in broadcast.role_name:
        return await message.answer("Великолепная версия!")

    await message.answer("Следующая версия!")


@router.message_reaction()
async def command_reaction_handler(
    event: MessageReactionUpdated,
    state: FSMContext,
    user: User,
    repo: RequestsRepo,
) -> None:
    m = await event.bot.set_message_reaction(
        chat_id=user.telegram_id,
        message_id=event.message_id,
        reaction=[ReactionTypeEmoji(emoji="👌")],
    )
    data = await state.get_data()
    reaction = event.new_reaction[0].emoji

    match reaction:
        case "👏":
            msg = await event.bot.edit_message_caption(
                chat_id=user.telegram_id,
                message_id=event.message_id,
                caption="Добавлен в избранное",
            )
            print(msg.audio.file_id)

        case "❤":
            caption = "Выпуск добавлен в избранное"

            msg = await event.bot.edit_message_caption(
                chat_id=user.telegram_id,
                message_id=event.message_id,
                caption=caption,
            )

            broadcast = await repo.broadcasts.get_broadcast_by_file_id(
                file_id=msg.audio.file_id
            )
            if user.show_role_name:
                caption = (
                    f"Выпуск добавлен в избранное"
                    f"<b>{broadcast.role_name}</b> "
                    f"<u>{broadcast.release_date}</u>"
                    if user.show_role_name
                    else "Выпуск добавлен в избранное"
                )
                await msg.edit_caption(caption=caption)

            print(broadcast.role_name)


@router.message_reaction_count()
async def command_reaction_handler2(
    event: Message,
    repo: RequestsRepo,
    state: FSMContext,
) -> None:

    data = await state.get_data()
    reaction = event.new_reaction[0].emoji
    message: Message = data["message"]
    broadcast = data["broadcast"]

    match reaction:
        case "👏":

            await message.edit_media(
                media=InputMediaAudio(
                    media=broadcast.telegram_file_id,
                    title=broadcast.role_name,
                    performer="Фрэнки - Шоу",
                ),
                reply_markup=None,
            )
        case "❤":
            await message.bot.send_message(
                text=f"<b>{broadcast.role_name}</b> добавлен в избранное",
                chat_id=message.chat.id,
            )
