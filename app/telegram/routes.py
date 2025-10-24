from aiogram import Dispatcher, F, Bot
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery

from app.dal import MessagesDAL, UsersDAL
from app.models import MessageModel, MessageType
from app.settings import Settings
from app.telegram.handlers.accept import handle_accept
from app.telegram.handlers.resume import handle_file
from app.telegram.handlers.start import handle_start, agreement_keyboard


def setup_routes(dp: Dispatcher, bot: Bot, settings: Settings) -> None:
    @dp.message(CommandStart())
    async def _start(message: Message):
        await handle_start(message, settings)

    @dp.callback_query(F.data == settings.callback_data)
    async def _accept(callback: CallbackQuery):
        user = await UsersDAL.get_user(callback.from_user.id)
        assert user is not None

        if user.accepted_rules:
            await callback.answer("Пользовательское соглашение уже принято. Пришлите PDF или DOCX с резюме.")
        else:
            await handle_accept(user, callback)

    @dp.message(F.document)
    async def _resume(message: Message):
        user = await UsersDAL.get_user(message.from_user.id)
        assert user is not None

        await handle_file(user, bot, message, settings)

    @dp.message(F.document)
    async def _resume(message: Message):
        user = await UsersDAL.get_user(message.from_user.id)
        assert user is not None

        await handle_file(user, bot, message, settings)

    @dp.message(F.text)
    async def _any_text(message: Message):
        user = await UsersDAL.get_user(message.from_user.id)
        assert user is not None

        await MessagesDAL.insert(
            MessageModel(
                type=MessageType.TEXT,
                message_id=message.message_id,
                text=message.text or "",
                chat_id=message.chat.id,
                user_id=user.tg_user_id,
            )
        )
        if user.accepted_rules:
            await message.answer("Пришлите PDF или DOCX с резюме.")
        else:
            await message.answer(
                "Пожалуйста, примите соглашение по кнопке перед продолжением использования бота",
                reply_markup=agreement_keyboard(settings),
            )
