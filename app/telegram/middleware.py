from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware, Bot
from aiogram.types import Message, CallbackQuery, BotCommand, BotCommandScopeChat, Update
from aiogram.fsm.context import FSMContext

from app.telegram.commander import setup_commands


class CommandsSyncMiddleware(BaseMiddleware):
    """
    Shows commands when user is not in any scene (FSM state is None),
    and clears commands when inside a scene.
    Caches last applied state per chat to avoid extra API calls.
    """
    def __init__(self) -> None:
        self._chat_visibility: Dict[int, bool] = {}

    async def __call__(
        self,
        handler: Callable[[Any, Dict[str, Any]], Awaitable[Any]],
        event: Any,
        data: Dict[str, Any],
    ) -> Any:

        result = await handler(event, data)
        print("HELLO", data.get("state"))
        await self._hide_of_show_buttons(event, data)

        return result

    async def _hide_of_show_buttons(self, event: Any, data: dict[str, Any]) -> None:
        bot: Bot = data.get("bot")  # provided by aiogram
        state: FSMContext = data.get("state")  # provided by aiogram

        chat_id = None
        if isinstance(event, Message):
            chat_id = event.chat.id
        elif isinstance(event, Update):
            if event.message:
                chat_id = event.message.chat.id
            elif event.callback_query and event.callback_query.message:
                chat_id = event.callback_query.message.chat.id
        elif isinstance(event, CallbackQuery) and event.message:
            chat_id = event.message.chat.id

        print(bot, state, chat_id)
        if bot and state and chat_id is not None:
            current_state = await state.get_state()
            should_show = current_state is None
            last = self._chat_visibility.get(chat_id)

            print(f"Сейчас пользователь видит {last}, должен ли: {should_show} (состояние: {current_state})")
            if last is None or last != should_show:
                try:
                    if should_show:
                        await setup_commands(chat_id, bot)
                    else:
                        # Clear commands for this chat while inside a scene
                        await bot.set_my_commands(commands=[], scope=BotCommandScopeChat(chat_id=chat_id))
                except Exception:
                    # Do not block the update on command sync errors
                    pass
                else:
                    self._chat_visibility[chat_id] = should_show
