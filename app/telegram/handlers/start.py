import time

from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup

from app.dal import UsersDAL, MessagesDAL
from app.models import MessageModel, MessageType
from app.settings import Settings



WELCOME_TEXT = """
Привет! Ты только что подключился к боту, который сделает твоё резюме идеальным🚀

Этот бот на базе ИИ даст конкретные рекомендации, чтобы ты мог прокачать его и адаптировать под несколько вакансий.

Давай начнём?
"""

def agreement_keyboard(settings: Settings) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="Принять пользовательское соглашение!", callback_data=settings.callback_data)
    ]])
    return kb


async def handle_start(message: Message, settings: Settings) -> None:
    user = await UsersDAL.ensure_user_from_message(message)

    await MessagesDAL.insert(
        MessageModel(
            type=MessageType.TEXT,
            message_id=message.message_id,
            text=message.text,
            chat_id=message.chat.id,
            user_id=message.from_user.id if message.from_user else "",
        )
    )

    if user.accepted_rules:
        await message.answer("С возвращением! Активируйте команду /analysis для анализа реюме.")
        return

    await message.answer(WELCOME_TEXT)
    time.sleep(2)
    parts = [
        "Для начала — немного формальностей. Чтобы мы могли работать с твоим резюме, нужно твоё согласие на обработку персональных данных. Без этого никак.",
        ""
        f"Пользовательское соглашение: {settings.user_agreement_url}",
        f"Обработка персональных данных: {settings.privacy_url}"
    ]
    await message.answer("\n\n".join(parts), reply_markup=agreement_keyboard(settings))
