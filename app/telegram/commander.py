from aiogram import Bot
from aiogram.types import BotCommand, BotCommandScopeChat


async def setup_commands(chat_id: int | None, bot: Bot):
    await bot.set_my_commands(
        commands=[
            BotCommand(command="analysis", description="Анализ резюме"),
            BotCommand(command="subscription", description="Покупка подписки"),
        ],
        scope=BotCommandScopeChat(chat_id=chat_id) if chat_id is not None else None,
    )

