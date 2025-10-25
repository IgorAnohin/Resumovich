from __future__ import annotations
import asyncio, logging, os
from aiogram import Bot, Dispatcher
from dotenv import load_dotenv
import sentry_sdk
from sentry_sdk.integrations.asyncio import AsyncioIntegration
from sentry_sdk.integrations.logging import LoggingIntegration
from sentry_sdk.integrations.aiohttp import AioHttpIntegration
from sentry_sdk.integrations.openai_agents import OpenAIAgentsIntegration

from app.telegram.commander import setup_commands
from app.telegram.routes import setup_routes
from app.settings import get_settings
from app.db import init_db

logging.basicConfig(level=logging.INFO)

def init_sentry(dsn: str | None) -> None:
    if not dsn:
        return
    sentry_sdk.init(
        dsn=dsn,
        traces_sample_rate=0.05,
        enable_tracing=True,
        integrations=[
            LoggingIntegration(level=logging.INFO, event_level=logging.ERROR),
            AioHttpIntegration(),
            AsyncioIntegration(),
            OpenAIAgentsIntegration()
        ],
        environment=os.environ.get("ENVIRONMENT", "production"),
        release=os.environ.get("RELEASE", "resume-bot@2"),
        send_default_pii=True,
    )


async def async_main() -> None:
    load_dotenv()
    settings = get_settings()

    # llm_service = LLMService.build(settings)
    # result = await llm_service.full_feedback("Test resume text for LLM initialization.", "")
    # print(result)

    init_sentry(settings.sentry_dsn)
    await init_db(settings.mongo_dsn, settings.db_name)

    bot = Bot(token=settings.telegram_token, parse_mode=None)
    tg_messages_dispatcher = Dispatcher(settings=settings)
    setup_routes(tg_messages_dispatcher)
    await setup_commands(None, bot)

    await tg_messages_dispatcher.start_polling(bot, close_bot_session=True)


def main() -> None:
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
