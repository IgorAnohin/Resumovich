import io, logging
from datetime import datetime

from aiogram import Bot
from aiogram.types import Message

from app.cv_analyzer.static import analyze_resume_text
from app.cv_analyzer.llm import LLMService
from app.dal import MessagesDAL, AnalyticsDAL, UsersDAL
from app.models import MessageModel, Analysis, Mode, User, AnalysisDetail, MessageType
from app.settings import Settings
from app.storage import save_upload
from app.telegram.handlers.start import agreement_keyboard
from app.utils import extract_text_auto

logger = logging.getLogger(__name__)


async def handle_file(user: User, bot: Bot, message: Message, settings: Settings) -> None:
    await MessagesDAL.insert(
        MessageModel(
            type=MessageType.DOCUMENT,
            message_id=message.message_id,
            text=message.caption or "",
            chat_id=message.chat.id,
            user_id=message.from_user.id if message.from_user else None,
            file_name=message.document.file_name,
        )
    )

    if not user.accepted_rules:
        await message.answer("Пожалуйста, примите соглашение по кнопке выше перед продолжением использования бота", reply_markup=agreement_keyboard(settings))
        return
    if not message.document:
        await message.answer("Пожалуйста, отправьте файл своего резюме в PDF или DOCX формате")
        return

    # download bytes
    try:
        text = await get_text_from_message(bot, message, settings.data_dir)
    except:
        await message.answer("Не удалось извлечь текст из файла. Пожалуйста, убедитесь, что это PDF или DOCX с текстом.")
        raise

    # Heuristic score
    heuristic = analyze_resume_text(text)
    score = heuristic.score

    llm_service = LLMService.build(settings)
    if llm_service:
        js = await llm_service.score_resume(text)
        if isinstance(js, dict) and isinstance(js.get("score"), int):
            score = max(0, min(100, int(js["score"])))

    # Полный отчёт
    if user.subscription_until < datetime.utcnow() and user.one_time_full_left <= 0:
        await AnalyticsDAL.insert(
            Analysis(
                user_id=message.from_user.id,
                filename=message.document.file_name,
                details=[heuristic],
                mode=Mode.SCORE_ONLY,
            )
        )
        await message.answer(
            f"Ваша оценка: {score}/100. Полный отчёт и конкретные рекомендации доступны в PRO. Команда: /buy_pro"
        )
        return

    detail = await llm_service.full_feedback(text)

    # Отправляем скоринг всем
    await message.answer(f"Оценка резюме: {detail.score or score}/100")

    if user.one_time_full_left > 0:
        await UsersDAL.consume_one_time_full(message.from_user.id)

    await AnalyticsDAL.insert(
        Analysis(
            user_id=message.from_user.id,
            filename=message.document.file_name,
            details=[detail, heuristic],
            mode=Mode.FULL,
        )
    )

    # Ответ пользователю
    parts = []
    if detail.strengths:
        parts.append("Сильные стороны:\n" + "\n".join(f"• {s}" for s in detail.strengths))
    if detail.problems:
        parts.append("Проблемы:\n" + "\n".join(f"• {p}" for p in detail.problems))
    if detail.actions:
        parts.append("Что сделать:\n" + "\n".join(f"• {a}" for a in detail.actions[:10]))
    await message.answer("\n\n".join(parts) or "Готово. Детали сформированы.")


async def get_text_from_message(bot: Bot, message: Message, data_dir: str) -> str:
    tg_file = await bot.get_file(message.document.file_id)
    buf = io.BytesIO()
    await bot.download_file(tg_file.file_path, buf)
    data = buf.getvalue()
    filename = message.document.file_name or f"resume_{message.document.file_id}"

    # Save locally
    path = save_upload(data_dir, message.from_user.id, filename, data)

    # Extract text
    return extract_text_auto(path)
