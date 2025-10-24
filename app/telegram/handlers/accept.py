from aiogram.types import CallbackQuery

from app.dal import UsersDAL, MessagesDAL
from app.models import MessageModel, User, MessageType


async def handle_accept(user: User, callback: CallbackQuery) -> None:
    await UsersDAL.accept_rules(user.tg_user_id)

    await callback.answer("Соглашение принято")
    await callback.message.answer(
        "Бот оценивает ваше резюме (0–100) бесплатно. Полный отчёт доступен платно. Первый раз — можем показать как демо.\n\n"
        "Грузите PDF/DOCX и смотрите результат."
    )
    await MessagesDAL.insert(
        MessageModel(
            type=MessageType.CALLBACK,
            message_id=callback.message.message_id if callback.message else -1,
            text="",
            chat_id=callback.message.chat.id if callback.message else -1,
            user_id=user.tg_user_id,
            callback_data=callback.data,
        )
    )

