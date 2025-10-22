from __future__ import annotations
import asyncio, io, os, logging
from datetime import datetime

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from .config import Settings
from .db import db
from .storage import save_upload
from .utils import extract_text_auto
from .analyzer import analyze_resume_text
from .llm import build_client_from_env, score_resume as llm_score_resume, full_feedback as llm_full_feedback
from .monitoring import REQUESTS, FAILURES, LLM_LATENCY

logger = logging.getLogger(__name__)

def agreement_keyboard() -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="Принять пользовательское соглашение!", callback_data="accept_rules")
    ]])
    return kb

async def ensure_user(message: Message, settings: Settings) -> dict:
    u = message.from_user
    assert u is not None
    name = ((u.first_name or "") + " " + (u.last_name or "")).strip() or u.username or "Без имени"
    existing = await db().users.find_one({"tg_user_id": u.id})
    if existing:
        return existing
    doc = {
        "tg_user_id": u.id,
        "tg_chat_id": message.chat.id,
        "name": name,
        "accepted_rules": False,
        "plan": "FREE",
        "subscription_until": None,
        "one_time_full_left": int(os.environ.get("FREE_ONE_TIME_FULL", "1")),
        "cover_packs_left": 0,
        "hr_reviews_left": 0,
        "created_at": datetime.utcnow(),
    }
    await db().users.insert_one(doc)
    return doc

async def handle_start(message: Message, settings: Settings) -> None:
    await ensure_user(message, settings)
    parts = [
        "Приветствуем вас в нашем боте. Он нужен для анализа ваших резюме.",
        "",
        "Для продолжения использования бота необходимо принять условия пользовательского соглашения и обработки персональных данных.",
    ]
    if settings.user_agreement_url:
        parts.append(f"Пользовательское соглашение: {settings.user_agreement_url}")
    if settings.privacy_url:
        parts.append(f"Обработка персональных данных: {settings.privacy_url}")
    await message.answer("\n\n".join(parts), reply_markup=agreement_keyboard())

    await db().messages.insert_one({
        "type": "text",
        "message_id": message.message_id,
        "text": message.text or "",
        "chat_id": message.chat.id,
        "user_id": message.from_user.id if message.from_user else None,
        "created_at": datetime.utcnow(),
    })

async def handle_accept(callback: CallbackQuery, settings: Settings) -> None:
    u = callback.from_user
    assert u is not None
    await db().users.update_one({"tg_user_id": u.id}, {"$set": {"accepted_rules": True, "updated_at": datetime.utcnow()}})
    await callback.answer("Соглашение принято")
    await callback.message.answer(
        "Бот оценивает ваше резюме (0–100) бесплатно. Полный отчёт доступен платно. Первый раз — можем показать как демо.\n\n"
        "Грузите PDF/DOCX и смотрите результат. Команды: /pricing, /buy_pro, /cover"
    )
    await db().messages.insert_one({
        "type": "callback",
        "message_id": callback.message.message_id if callback.message else None,
        "text": "",
        "chat_id": callback.message.chat.id if callback.message else None,
        "user_id": u.id,
        "data": callback.data,
        "created_at": datetime.utcnow(),
    })

def has_active_pro(user: dict) -> bool:
    until = user.get("subscription_until")
    plan = user.get("plan", "FREE")
    if plan != "PRO" or not until:
        return False
    if isinstance(until, str):
        try:
            until = datetime.fromisoformat(until)
        except Exception:
            return False
    return until >= datetime.utcnow()

async def send_paywall(message: Message, score: int) -> None:
    await message.answer(
        f"Ваша оценка: {score}/100. Полный отчёт и конкретные рекомендации доступны в PRO. Команда: /buy_pro"
    )

def is_allowed_full(user: dict) -> bool:
    if has_active_pro(user):
        return True
    return int(user.get("one_time_full_left", 0)) > 0

async def consume_one_time_full(user_id: int) -> None:
    await db().users.update_one({"tg_user_id": user_id, "one_time_full_left": {"$gt": 0}}, {"$inc": {"one_time_full_left": -1}})

async def handle_file(bot: Bot, message: Message, settings: Settings) -> None:
    user = await ensure_user(message, settings)
    if not user.get("accepted_rules", False):
        await message.answer("Пожалуйста, примите соглашение по кнопке выше перед продолжением использования бота", reply_markup=agreement_keyboard())
        return
    if not message.document:
        await message.answer("Пожалуйста, отправьте файл своего резюме в PDF или DOCX формате")
        return

    # download bytes
    tgfile = await bot.get_file(message.document.file_id)
    buf = io.BytesIO()
    await bot.download_file(tgfile.file_path, buf)
    data = buf.getvalue()
    filename = message.document.file_name or f"resume_{message.document.file_id}"

    # Save locally
    path = save_upload(os.environ.get("DATA_DIR", "/data/uploads"), message.from_user.id, filename, data)

    # Extract text
    text = extract_text_auto(path)
    if not text.strip():
        FAILURES.labels(stage="parse").inc()
        await message.answer("Не удалось извлечь текст. Проверьте, что PDF не отсканирован, или пришлите DOCX.")
        return

    # Heuristic score
    from .analyzer import analyze_resume_text
    heuristic = analyze_resume_text(text)
    score = heuristic["score"]
    REQUESTS.labels(type="score").inc()

    client = build_client_from_env()
    # Если есть LLM, уточним скоринг и/или сделаем полный анализ
    if client:
        try:
            import time
            t0 = time.perf_counter()
            js = await llm_score_resume(client, text)
            LLM_LATENCY.observe(time.perf_counter() - t0)
            if isinstance(js, dict) and isinstance(js.get("score"), int):
                score = max(0, min(100, int(js["score"])))
        except Exception:
            FAILURES.labels(stage="llm").inc()

    # Сохраняем базовую запись анализа
    base_doc = {
        "user_id": message.from_user.id if message.from_user else None,
        "file_path": path,
        "filename": filename,
        "created_at": datetime.utcnow(),
        "score": score,
        "mode": "score_only",
        "payload": {"heuristic": heuristic},
    }
    ins = await db().analyses.insert_one(base_doc)

    # Отправляем скоринг всем
    await message.answer(f"Оценка резюме: {score}/100")    

    # Полный отчёт
    if is_allowed_full(user):
        REQUESTS.labels(type="full").inc()
        detail = None
        if client:
            try:
                import time
                t0 = time.perf_counter()
                detail = await llm_full_feedback(client, text)
                LLM_LATENCY.observe(time.perf_counter() - t0)
            except Exception:
                FAILURES.labels(stage="llm").inc()

        if not detail:
            # fallback: используем эвристики как 'actions'
            detail = {
                "score": score,
                "strengths": [],
                "problems": heuristic.get("findings", []),
                "actions": heuristic.get("suggestions", []),
                "sections": {},
            }

        # сохраним и отправим
        await db().analyses.update_one({"_id": ins.inserted_id}, {"$set": {"mode": "full", "payload.detail": detail}})
        if not has_active_pro(user):
            await consume_one_time_full(message.from_user.id)

        # Ответ пользователю
        parts = []
        strengths = detail.get("strengths") or []
        problems = detail.get("problems") or []
        actions = detail.get("actions") or []
        if strengths:
            parts.append("Сильные стороны:\n" + "\n".join(f"• {s}" for s in strengths))
        if problems:
            parts.append("Проблемы:\n" + "\n".join(f"• {p}" for p in problems))
        if actions:
            parts.append("Что сделать:\n" + "\n".join(f"• {a}" for a in actions[:10]))
        await message.answer("\n\n".join(parts) or "Готово. Детали сформированы.")
    else:
        await send_paywall(message, score)

    # лог
    await db().messages.insert_one({
        "type": "document",
        "message_id": message.message_id,
        "text": message.caption or "",
        "chat_id": message.chat.id,
        "user_id": message.from_user.id if message.from_user else None,
        "file_name": filename,
        "created_at": datetime.utcnow(),
    })

async def handle_text(message: Message, settings: Settings) -> None:
    if message.text and message.text.strip() == "/start":
        return
    await message.answer("Пришлите PDF или DOCX с резюме. Команды: /pricing, /buy_pro, /cover")

def setup_handlers(dp: Dispatcher, bot: Bot, settings: Settings) -> None:
    @dp.message(CommandStart())
    async def _start(message: Message):
        await handle_start(message, settings)

    @dp.callback_query(F.data == "accept_rules")
    async def _accept(callback: CallbackQuery):
        await handle_accept(callback, settings)

    @dp.message(F.document)
    async def _doc(message: Message):
        await handle_file(bot, message, settings)

    @dp.message(F.text)
    async def _any_text(message: Message):
        await handle_text(message, settings)
