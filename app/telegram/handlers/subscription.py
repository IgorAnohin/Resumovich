import uuid
from datetime import datetime, timedelta

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, LabeledPrice, PreCheckoutQuery, CallbackQuery, InlineKeyboardButton, \
    InlineKeyboardMarkup

from app.dal import UsersDAL, MessagesDAL
from app.models import MessageModel, MessageType
from app.settings import Settings

subscription_router = Router(name="subscription")

CALLBACK_DATA = "I_WANNA_PAY"


@subscription_router.message(Command("subscription"))
async def buy_subscription(message: Message, settings: Settings):
    user = await UsersDAL.get_user(message.from_user.id)

    # Log command
    await MessagesDAL.insert(
        MessageModel(
            type=MessageType.COMMAND,
            message_id=message.message_id,
            text=message.text or "",
            chat_id=message.chat.id,
            user_id=message.from_user.id if message.from_user else "",
        )
    )

    # Require T&C acceptance before purchase
    if not user.accepted_rules:
        await message.answer("Пожалуйста, используйте команду /start чтобы принять пользовательское соглашение.")
        return

    if not settings.payments_provider_token:
        await message.answer("Платежи временно недоступны. Попробуйте позже.")
        return

        # Price from settings (kopecks), fallback to 299.00 RUB
    price_kopecks = int(getattr(settings, "subscription_price_rub", 29900))
    price_rub = price_kopecks / 100.0

    # Offer message with payment button
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"👛Оплатить {price_rub:.2f} ₽", callback_data=CALLBACK_DATA)]
        ]
    )
    await message.answer(
        f"Мы предлагаем оформить подписку на 7 дней.\nСтоимость: {price_rub:.2f} ₽.\n"
        "Нажмите кнопку, чтобы перейти к оплате.",
        reply_markup=kb,
    )


@subscription_router.callback_query(F.data == CALLBACK_DATA)
async def accept(callback: CallbackQuery, settings: Settings):
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

    # Send Telegram invoice using YooMoney provider token
    try:
        await callback.message.answer_invoice(
            title="Подписка на 1 неделю",
            description="Доступ ко всем функциям на 7 дней.",
            provider_token=settings.payments_provider_token,
            currency="RUB",
            prices=[LabeledPrice(label="1 неделя подписки", amount=29900 )],  # 299.00 RUB
            payload=f"sub_1w:{user.tg_user_id}:{uuid.uuid4().hex}",
            start_parameter="buy-subscription-1m",
            is_flexible=False,  # digital good, no shipping
        )
    except:
        await callback.message.answer("Не удалолось инициировать оплату. попробуйте позже или обратитесь в поддержку")
        raise


@subscription_router.pre_checkout_query()
async def pre_checkout(pre_checkout_query: PreCheckoutQuery):
    # Approve pre-checkout for digital goods
    await pre_checkout_query.answer(ok=True)


@subscription_router.message(F.successful_payment)
async def successful_payment(message: Message):
    # Log successful payment message
    await MessagesDAL.insert(
        MessageModel(
            type=MessageType.TEXT,
            message_id=message.message_id,
            text=f"successful_payment:{message.successful_payment.provider_payment_charge_id}",
            chat_id=message.chat.id,
            user_id=message.from_user.id if message.from_user else "",
        )
    )

    user = await UsersDAL.get_user(message.from_user.id)

    # Activate subscription for 7 days from now or extend if active
    now = datetime.now()
    base = user.subscription_until if user.subscription_until > now else now
    new_until = base + timedelta(days=7)

    # Persist subscription end date (implement this DAL method if missing)
    await UsersDAL.set_subscription_until(user.tg_user_id, new_until)

    # Notify user
    total = message.successful_payment.total_amount / 100.0
    currency = message.successful_payment.currency
    await message.answer(f"Оплата {total:.2f} {currency} прошла успешно! Подписка активна до {new_until:%d.%m.%Y}.")
