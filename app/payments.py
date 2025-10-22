from __future__ import annotations
from aiogram import Bot, F, Router
from aiogram.types import LabeledPrice, Message, PreCheckoutQuery, SuccessfulPayment
from aiogram.filters import Command
from datetime import datetime, timedelta
from .config import Settings
from .db import db

router = Router(name="payments")

def _price(amount_rub: int) -> list[LabeledPrice]:
    return [LabeledPrice(label="Оплата", amount=amount_rub)]

@router.message(Command("pricing"))
async def pricing(msg: Message, settings: Settings):
    text = (
        "Тарифы:\n"
        f"• PRO на {settings.pro_days_on_payment} дней: {settings.pro_price_rub/100:.2f} RUB — /buy_pro\n"
        f"• Разбор с HR: {settings.hr_review_price_rub/100:.2f} RUB — /buy_hr\n"
        f"• Пакет сопроводительных: {settings.cover_pack_price_rub/100:.2f} RUB — /buy_cover\n"
    )
    await msg.answer(text)

@router.message(Command("buy_pro"))
async def buy_pro(msg: Message, bot: Bot, settings: Settings):
    if not settings.payments_provider_token:
        await msg.answer("Платёжный провайдер не настроен.")
        return
    await bot.send_invoice(
        chat_id=msg.chat.id,
        title="Подписка PRO",
        description=f"Доступ к полным отчётам на {settings.pro_days_on_payment} дней",
        payload="BUY_PRO",
        provider_token=settings.payments_provider_token,
        currency="RUB",
        prices=_price(settings.pro_price_rub)
    )

@router.message(Command("buy_hr"))
async def buy_hr(msg: Message, bot: Bot, settings: Settings):
    if not settings.payments_provider_token:
        await msg.answer("Платёжный провайдер не настроен.")
        return
    await bot.send_invoice(
        chat_id=msg.chat.id,
        title="Разбор с HR",
        description="Живой фидбек от HR. Мы свяжемся в чате.",
        payload="BUY_HR",
        provider_token=settings.payments_provider_token,
        currency="RUB",
        prices=_price(settings.hr_review_price_rub)
    )

@router.message(Command("buy_cover"))
async def buy_cover(msg: Message, bot: Bot, settings: Settings):
    if not settings.payments_provider_token:
        await msg.answer("Платёжный провайдер не настроен.")
        return
    await bot.send_invoice(
        chat_id=msg.chat.id,
        title="Пакет сопроводительных писем",
        description="Генерация сопроводительных под вакансии.",
        payload="BUY_COVER",
        provider_token=settings.payments_provider_token,
        currency="RUB",
        prices=_price(settings.cover_pack_price_rub)
    )

@router.pre_checkout_query()
async def on_pre_checkout(pre: PreCheckoutQuery):
    await pre.answer(ok=True)

@router.message(F.successful_payment)
async def on_success_payment(msg: Message, settings: Settings):
    sp: SuccessfulPayment = msg.successful_payment
    payload = sp.invoice_payload
    user_id = msg.from_user.id if msg.from_user else None
    if not user_id:
        return
    if payload == "BUY_PRO":
        until = datetime.utcnow() + timedelta(days=settings.pro_days_on_payment)
        await db().users.update_one({"tg_user_id": user_id}, {"$set": {"plan": "PRO", "subscription_until": until}})
        await msg.answer("Готово: PRO активирован. Присылайте резюме для полного отчёта.")
    elif payload == "BUY_HR":
        await db().users.update_one({"tg_user_id": user_id}, {"$inc": {"hr_reviews_left": 1}})
        await msg.answer("Оплата принята. HR свяжется с вами в этом чате.")
    elif payload == "BUY_COVER":
        await db().users.update_one({"tg_user_id": user_id}, {"$inc": {"cover_packs_left": 1}})
        await msg.answer("Пакет сопроводительных активирован. Используйте команду /cover.")
