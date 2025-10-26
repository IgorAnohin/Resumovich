import uuid
from datetime import datetime, timedelta

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, LabeledPrice, PreCheckoutQuery, CallbackQuery, InlineKeyboardButton, \
    InlineKeyboardMarkup
from pydantic import BaseModel

from app.dal import UsersDAL, MessagesDAL
from app.models import MessageModel, MessageType
from app.settings import Settings

subscription_router = Router(name="subscription")


class Product(BaseModel):
    name: str
    description: str
    price: float
    callback_data: str
    emoji: str = "💼"

SUB_1_WEEK = Product(
        name="Подписка на 1 неделю",
        description="Доступ ко всем функциям на 7 дней.",
        emoji="🔓",
        price=299.0,
        callback_data="sub_1w",
    )

ONE_TIME_USAGE = Product(
        name="Разовая проверка резюме",
        description="Одноразовая проверка резюме без подписки.",
        emoji="💼",
        price=99.0,
        callback_data="single_check",
    )


PRODUCTS = [SUB_1_WEEK, ONE_TIME_USAGE]


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

    # Offer message with payment button
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"{product.emoji} {product.name} {product.price:.2f} ₽",
                    callback_data=product.callback_data,
                )
            ] for product in PRODUCTS
        ]
    )
    await message.answer(
        "Мы предлагаем 2 формата работы с нашим ботом:\n"
        "- Разовая покупка проверки резюме .\n"
        "- Недельная подписка на сервис с неограниченным количеством проверок .\n"
        "Нажмите кнопку, чтобы перейти к оплате.",
        reply_markup=kb,
    )


@subscription_router.callback_query(F.data == SUB_1_WEEK.callback_data)
async def buy_subscription(callback: CallbackQuery, settings: Settings):
    await buy_product(callback, SUB_1_WEEK, settings)


@subscription_router.callback_query(F.data == ONE_TIME_USAGE.callback_data)
async def buy_one_time(callback: CallbackQuery, settings: Settings):
    await buy_product(callback, ONE_TIME_USAGE, settings)


async def buy_product(callback: CallbackQuery, product: Product, settings: Settings):
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
            title=product.name,
            description=product.description,
            provider_token=settings.payments_provider_token,
            currency="RUB",
            prices=[LabeledPrice(label=product.name, amount=int(product.price * 100))],  # 299.00 RUB
            payload=f"{product.callback_data}:{user.tg_user_id}:{uuid.uuid4().hex}",
            start_parameter=product.callback_data,
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

    product = next(
        (p for p in PRODUCTS if message.successful_payment.invoice_payload.startswith(p.callback_data)),
        None
    )
    if not product:
        await message.answer("Произошла ошибка при обработке вашего платежа. Пожалуйста, свяжитесь с поддержкой.")
        raise

    user = await UsersDAL.get_user(message.from_user.id)

    if product.callback_data == SUB_1_WEEK.callback_data:
        # Grant one-time full check
        await UsersDAL.add_one_time_full_check(user.tg_user_id)
        await message.answer("Оплата прошла успешно! Вам предоставлена одноразовая полная проверка резюме.")
        return
    elif product.callback_data == ONE_TIME_USAGE.callback_data:
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
