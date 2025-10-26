import asyncio
import io, logging
import re
from datetime import datetime

import sentry_sdk
from aiogram import Bot, Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from pydantic import BaseModel

from app.cv_analyzer.static import analyze_resume_text
from app.cv_analyzer.llm import LLMService
from app.dal import MessagesDAL, AnalyticsDAL, UsersDAL, FileCheckingDAL
from app.models import MessageModel, Analysis, MessageType, AnalysisDetail, FileChecking
from app.settings import Settings
from app.storage import save_upload
from app.utils.long_messages import send_long_message
from app.utils.text_parser import extract_text_auto

logger = logging.getLogger(__name__)

analysis_router = Router(name="analyis")

CALLBACK_DATA = "skip_vacancy_details"


class AnalysisScene(StatesGroup):
    resume_waiting = State()
    vacancy_waiting = State()


class DocumentInfo(BaseModel):
    path: str
    data: str


@analysis_router.message(Command("analysis"))
async def analysis(message: Message, state: FSMContext):
    user = await UsersDAL.get_user(message.from_user.id)

    await MessagesDAL.insert(
        MessageModel(
            type=MessageType.COMMAND,
            message_id=message.message_id,
            text=message.text,
            chat_id=message.chat.id,
            user_id=message.from_user.id if message.from_user else "",
        )
    )

    if not user.accepted_rules:
        await message.answer("Пожалуйста, примите соглашение. Для этого воспользуйтесь командой /start")
        return

    # Полный отчёт
    if user.subscription_until < datetime.utcnow() and user.one_time_full_left <= 0:
        await message.answer(
            f"Оплатите подписку, чтобы пользоваться отчётами о резюме. Команда: /subscription"
        )
        return

    await state.set_state(AnalysisScene.resume_waiting)
    await message.answer("Пожалуйста, отправьте файл своего резюме в PDF или DOCX формате для анализа.")


@analysis_router.message(AnalysisScene.resume_waiting, F.document)
async def handle_resume(message: Message, state: FSMContext, bot: Bot, settings: Settings) -> None:
    await message.answer("Читаем файл...")

    # download bytes
    try:
        resume_info = await get_text_from_message(bot, message, settings.data_dir)
        await MessagesDAL.insert(
            MessageModel(
                type=MessageType.DOCUMENT,
                message_id=message.message_id,
                text="OK",
                chat_id=message.chat.id,
                user_id=message.from_user.id if message.from_user else None,
                file_name=message.document.file_name,
            )
        )

    except:
        await message.answer(
            "Не удалось извлечь текст из файла. Пожалуйста, убедитесь, что это PDF или DOCX с текстом. Или обратитесь в поддержку."
        )
        await MessagesDAL.insert(
            MessageModel(
                type=MessageType.DOCUMENT,
                message_id=message.message_id,
                text="ERROR",
                chat_id=message.chat.id,
                user_id=message.from_user.id if message.from_user else None,
                file_name=message.document.file_name,
            )
        )

        raise

    await message.answer("Проверяем файл...")

    llm_service = LLMService.build(settings.llm_settings)
    try:
        detail = await llm_service.check_resume_is_valid(
            resume_info.data,
        )
    except:
        await message.answer(
            "Произошла ошибка при проверке файла. Пожалуйста, попробуйте позже или обратитесь в поддержку."
        )
        raise

    if not detail.is_valid:
        await FileCheckingDAL.insert(FileChecking(
            user_id=message.from_user.id,
            filepath=resume_info.path,
            result=detail,
        ))
        await message.answer(
            f"Похоже, что это не резюме.\n\n"
            # f"{detail.reason}\n\n"
            "Пожалуйста, отправьте корректный файл описания вакансии текстом или в PDF/DOCX формате."
        )
        return

    # save file to analysis documents
    await state.update_data(resume_info=resume_info)

    # Add button to skip vacancy details
    await message.answer(
        "Файл получен.\n\n"
        "Теперь добавьте, если хотите, название вакансии или её описание. Можно сделать текстом или документом PDF/TXT."
        "Можете пропустить этот шаг и сразу получить анализ резюме.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="⏩ Без описания вакансии!", callback_data=CALLBACK_DATA)
        ]]),
    )
    await state.set_state(AnalysisScene.vacancy_waiting)


@analysis_router.message(AnalysisScene.vacancy_waiting, F.document)
async def handle_vacancy(message: Message, state: FSMContext, bot: Bot, settings: Settings) -> None:

    await message.answer("Читаем файл...")

    # download bytes
    try:
        vacancy_info = await get_text_from_message(bot, message, settings.data_dir)
        await MessagesDAL.insert(
            MessageModel(
                type=MessageType.DOCUMENT,
                message_id=message.message_id,
                text="OK",
                chat_id=message.chat.id,
                user_id=message.from_user.id if message.from_user else None,
                file_name=message.document.file_name,
            )
        )
    except:
        await MessagesDAL.insert(
            MessageModel(
                type=MessageType.DOCUMENT,
                message_id=message.message_id,
                text="ERROR",
                chat_id=message.chat.id,
                user_id=message.from_user.id if message.from_user else None,
                file_name=message.document.file_name,
            )
        )
        await message.answer(
            "Не удалось извлечь текст из файла. Пожалуйста, убедитесь, что это PDF или DOCX с текстом. Или обратитесь в поддержку."
        )
        raise


    llm_service = LLMService.build(settings.llm_settings)
    try:
        file_checking_result = await llm_service.check_resume_is_valid(
            vacancy_info.data,
        )
    except:
        await message.answer(
            "Произошла ошибка при проверке файла. Пожалуйста, попробуйте позже или обратитесь в поддержку."
        )
        raise

    if not file_checking_result.is_valid:
        await FileCheckingDAL.insert(FileChecking(
            user_id=message.from_user.id,
            filepath=vacancy_info.path,
            result=file_checking_result,
        ))
        await message.answer(
            f"Похоже, что это не описание вакансии.\n\n"
            # f"{file_checking_result.reason}\n\n"
            "Пожалуйста, отправьте корректный файл резюме в PDF или DOCX формате."
        )
        return

    data = await state.get_data()
    resume_info: DocumentInfo = data.get("resume_info")
    if not resume_info:
        await message.answer("Произошла ошибка. Пожалуйста, начните анализ заново командой /analysis.")
        await state.clear()
        return

    await process_resume(message, resume_info, vacancy_info, settings)


@analysis_router.message(AnalysisScene.vacancy_waiting)
async def handle_vacancy_text(message: Message, state: FSMContext, bot: Bot, settings: Settings) -> None:
    await MessagesDAL.insert(
        MessageModel(
            type=MessageType.TEXT,
            message_id=message.message_id,
            text=message.text or "",
            chat_id=message.chat.id,
            user_id=message.from_user.id if message.from_user else None,
        )
    )

    data = await state.get_data()
    resume_info: DocumentInfo = data.get("resume_info")
    if not resume_info:
        await message.answer("Произошла ошибка. Пожалуйста, начните анализ заново командой /analysis.")
        await state.clear()
        return

    await process_resume(message, resume_info, DocumentInfo(path="", data=message.text), settings)


@analysis_router.callback_query(AnalysisScene.vacancy_waiting, F.data == CALLBACK_DATA)
async def handle_skip_vacancy(callback: CallbackQuery, state: FSMContext, settings: Settings) -> None:
    await MessagesDAL.insert(
        MessageModel(
            type=MessageType.CALLBACK,
            message_id=callback.message.message_id if callback.message else -1,
            text="",
            chat_id=callback.message.chat.id if callback.message else -1,
            user_id=callback.from_user.id,
            callback_data=callback.data,
        )
    )

    data = await state.get_data()
    resume_info: DocumentInfo = data.get("resume_info")
    if not resume_info:
        await callback.message.answer("Произошла ошибка. Пожалуйста, начните анализ заново командой /analysis.")
        await state.clear()
        return

    await process_resume(
        callback.message,
        resume_info,
        DocumentInfo(path="", data=""),
        settings,
    )
    await state.clear()


async def process_resume(message: Message, cv_info: DocumentInfo, vacancy_info: DocumentInfo,
                         settings: Settings) -> None:
    heuristic = analyze_resume_text(cv_info.data)
    score = heuristic.score

    await message.answer("Анализируем резюме...\nЭто может занять несколько минут.")
    try:
        llm_service = LLMService.build(settings.llm_settings)
        detail = await llm_service.full_feedback(
            cv_info.data,
            vacancy_info.data,
        )
    except:
        await message.answer(
            "Произошла ошибка при анализе резюме. Пожалуйста, попробуйте позже или обратитесь в поддержку."
        )
        raise

    await AnalyticsDAL.insert(
        Analysis(
            user_id=message.from_user.id,
            filepaths=[cv_info.path, vacancy_info.path],
            details=[detail, heuristic],
        )
    )

    if detail.ok:
        await send_ok_message(detail, message)
    else:
        await send_raw_message(detail, message)

    user = await UsersDAL.get_user(message.from_user.id)
    await UsersDAL.consume_one_time_full(user.tg_user_id)
    await message.answer(
        "На этом демонстрация окончена.\n\n"
        "Если хотите узнать, как наш бот отреагирует на новое резюме, купите подписку. Команда /subscription"
    )


def _escape_md_v2(text: str) -> str:
    # Telegram MarkdownV2 requires escaping these characters
    return re.sub(r'([_*[\]()~`>#\+\-=|{}\.!])', r'\\\1', text)


async def send_ok_message(detail: AnalysisDetail, message: Message) -> None:
    score_str = str(detail.score) if detail.score is not None else "—"
    sections: list[str] = [f"*📊 Оценка резюме: {_escape_md_v2(score_str)}/100*"]

    if detail.strengths:
        strengths = "\n".join(f"• {_escape_md_v2(s)}" for s in detail.strengths)
        sections.append(f"*✅ Сильные стороны*\n{strengths}")

        full_text = "\n\n".join(sections)
        await send_long_message(message, full_text, parse_mode="MarkdownV2")
        sections = []

    if detail.problems:
        problems = "\n".join(f"• {_escape_md_v2(p)}" for p in detail.problems)
        sections.append(f"*⚠️ Проблемы*\n{problems}")

        full_text = "\n\n".join(sections)
        await send_long_message(message, full_text, parse_mode="MarkdownV2")
        sections = []

    if detail.actions:
        actions = "\n".join(f"• {_escape_md_v2(a)}" for a in detail.actions[:10])
        sections.append(f"*🛠 Что сделать*\n{actions}")

        full_text = "\n\n".join(sections)
        await send_long_message(message, full_text, parse_mode="MarkdownV2")
        sections = []

    if sections:
        full_text = "\n\n".join(sections)
        await send_long_message(message, full_text, parse_mode="MarkdownV2")


async def send_raw_message(detail: AnalysisDetail, message: Message) -> None:
    sentry_sdk.capture_message(
        f"LLM resume analysis parsing failed for user. {message.from_user.id=} {message.message_id=}",
        level="warning",
    )
    await message.answer(
        "Не удалось корректно проанализировать резюме. Вот что вернуло LLM (возможно, формат ответа не соответствует ожидаемому):"
    )
    await send_long_message(message, _escape_md_v2(detail.raw), parse_mode="MarkdownV2")


async def get_text_from_message(bot: Bot, message: Message, data_dir: str) -> DocumentInfo:
    tg_file = await bot.get_file(message.document.file_id)
    buf = io.BytesIO()
    await bot.download_file(tg_file.file_path, buf)
    data = buf.getvalue()
    filename = message.document.file_name or f"resume_{message.document.file_id}"

    # Save locally
    path = save_upload(data_dir, message.from_user.id, filename, data)

    return DocumentInfo(
        path=path,
        data=extract_text_auto(path),
    )
