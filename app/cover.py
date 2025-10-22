from __future__ import annotations
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from datetime import datetime
from .db import db
from .llm import build_client_from_env
from .monitoring import REQUESTS, FAILURES, LLM_LATENCY

router = Router(name="cover")

@router.message(Command("cover"))
async def cover(msg: Message):
    user_id = msg.from_user.id if msg.from_user else None
    if not user_id:
        return
    user = await db().users.find_one({"tg_user_id": user_id})
    if not user:
        await msg.answer("/start, потом /cover ещё раз.")
        return

    if user.get("cover_packs_left", 0) <= 0 and user.get("plan") != "PRO":
        await msg.answer("Для генерации сопроводительных нужен активный пакет или PRO. Команда: /buy_cover или /buy_pro.")
        return

    # Берём последний анализ, если есть
    last = await db().analyses.find_one({"user_id": user_id}, sort=[("created_at", -1)])
    if not last:
        await msg.answer("Сначала отправьте резюме, затем вызовите /cover.")
        return

    vacancy = (msg.text or "").split(" ", 1)
    vacancy_text = vacancy[1] if len(vacancy) > 1 else ""
    if not vacancy_text.strip():
        await msg.answer("Пришлите команду так: /cover Описание вакансии или её ключевые требования.")
        return

    client = build_client_from_env()
    if not client:
        await msg.answer("LLM не настроен. Укажите LLM_BASE_URL, LLM_API_KEY, LLM_MODEL_NAME.")
        return

    REQUESTS.labels(type="cover").inc()
    import time
    t0 = time.perf_counter()
    try:
        data = await client.gen_json(
            system="Вы пишете краткое сопроводительное письмо под вакансию на основе резюме. Верните JSON: {\"letter\": string}. Русский язык, 120–180 слов.",
            user=f"Резюме (сжатое): {last.get('payload', {}).get('heuristic', {})}. Вакансия: {vacancy_text}"
        )
        LLM_LATENCY.observe(time.perf_counter() - t0)
    except Exception:
        FAILURES.labels(stage="llm").inc()
        await msg.answer("Не удалось сгенерировать письмо.")
        return

    letter = data.get("letter") or ""
    if not letter.strip():
        await msg.answer("Ответ модели пуст.")
        return

    if user.get("plan") != "PRO" and user.get("cover_packs_left", 0) > 0:
        await db().users.update_one({"tg_user_id": user_id}, {"$inc": {"cover_packs_left": -1}})

    await msg.answer(letter.strip())
