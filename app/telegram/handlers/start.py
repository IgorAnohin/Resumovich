import time

from aiogram import Router, F
from aiogram.filters import CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery

from app import settings
from app.dal import UsersDAL, MessagesDAL
from app.models import MessageModel, MessageType, User
from app.settings import Settings

from aiogram.fsm.state import StatesGroup, State

from app.telegram.handlers.analysis import AnalysisScene


class TermsScene(StatesGroup):
    terms_accept_waiting = State()

WELCOME_TEXT = """
Привет! Ты только что подключился к боту, который сделает твоё резюме идеальным🚀

Этот бот на базе ИИ даст конкретные рекомендации, чтобы ты мог прокачать его и адаптировать под несколько вакансий.

Давай начнём?
"""


start_router = Router(name="start")


CALLBACK_DATA = "accept_user_agreement"


def agreement_keyboard() -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅Принять пользовательское соглашение!", callback_data=CALLBACK_DATA)
    ]])
    return kb

@start_router.message(CommandStart())
async def start(message: Message, state: FSMContext, settings: Settings):
    user = await UsersDAL.ensure_user_from_message(message)

    await MessagesDAL.insert(
        MessageModel(
            type=MessageType.COMMAND,
            message_id=message.message_id,
            text=message.text,
            chat_id=message.chat.id,
            user_id=message.from_user.id if message.from_user else "",
        )
    )

    if user.accepted_rules:
        await state.clear()
        await message.answer("С возвращением! Активируйте команду /analysis для анализа реюме.")
        return

    await state.set_state(TermsScene.terms_accept_waiting)

    await message.answer(WELCOME_TEXT)
    time.sleep(2)

    parts = [
        "Для начала — немного формальностей. Чтобы мы могли работать с твоим резюме, нужно твоё согласие на обработку персональных данных. Без этого никак.",
        ""
        f"Пользовательское соглашение: {settings.user_agreement_url}",
        f"Обработка персональных данных: {settings.privacy_url}"
    ]
    await message.answer("\n\n".join(parts), reply_markup=agreement_keyboard())


@start_router.callback_query(TermsScene.terms_accept_waiting, F.data == CALLBACK_DATA)
async def accept(callback: CallbackQuery, state: FSMContext):
    user = await UsersDAL.get_user(callback.from_user.id)
    assert user is not None

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

    if user.accepted_rules:
        await callback.answer("Пользовательское соглашение уже принято.\nПожалуйста, используйте комманде /analysis для анализа резюме.")
        await state.clear()
    else:
        await UsersDAL.accept_rules(user.tg_user_id)

        await callback.answer("Соглашение принято!")

        await state.set_state(AnalysisScene.resume_waiting)
        await callback.message.answer(
            "Давай я покажу, как работает наш анализ рюзему и насколько круто.\n"
            "Пришли своё резюме в формате Word, PDF или TXT. (выгзузка с HH тоже подойдёт)"
        )


@start_router.message(TermsScene.terms_accept_waiting)
async def block_everything_until_accept(message: Message):
    await message.answer(
        "Пожалуйста, примите пользовательское соглашение, чтобы продолжить.",
        reply_markup=agreement_keyboard(),
    )
