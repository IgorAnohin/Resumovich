from aiogram import Router, F
from aiogram.types import Message

from app.dal import UsersDAL, MessagesDAL
from app.models import MessageModel, MessageType
from app.settings import Settings

fallback_router = Router(name="fallback")


@fallback_router.message(F.text)
async def any_text(message: Message, settings: Settings):
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
        await message.answer("Пожалуйста, используйте команду /analysis для анализа резюме.")
    else:
        await message.answer(
            "Пожалуйста, используйте команду /start чтобы принять пользовательское соглашение.",
        )
