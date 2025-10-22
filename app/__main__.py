from __future__ import annotations
import asyncio, logging, os
from aiogram import Bot, Dispatcher
from dotenv import load_dotenv
import sentry_sdk
from sentry_sdk.integrations.logging import LoggingIntegration
from sentry_sdk.integrations.aiohttp import AioHttpIntegration

from .config import get_settings, Settings
from .db import init_db
from .bot import setup_handlers
from .payments import router as payments_router
from .cover import router as cover_router
from .monitoring import app as monitoring_app

import uvicorn
from fastapi import FastAPI

logging.basicConfig(level=logging.INFO)

def init_sentry(dsn: str | None) -> None:
    if not dsn:
        return
    sentry_sdk.init(
        dsn=dsn,
        traces_sample_rate=0.05,
        enable_tracing=True,
        integrations=[LoggingIntegration(level=logging.INFO, event_level=logging.ERROR), AioHttpIntegration()],
        environment=os.environ.get("ENVIRONMENT", "production"),
        release=os.environ.get("RELEASE", "resume-bot@2"),
    )

async def start_metrics_server(host: str, port: int) -> None:
    uvconfig = uvicorn.Config(monitoring_app, host=host, port=port, log_level="info")
    server = uvicorn.Server(uvconfig)
    await server.serve()

async def async_main() -> None:
    load_dotenv()
    settings = get_settings()
    init_sentry(settings.sentry_dsn)
    await init_db(settings.mongo_dsn, settings.db_name)

    bot = Bot(token=settings.telegram_token, parse_mode=None)
    tg_messages_dispatcher = Dispatcher()
    # Routers
    tg_messages_dispatcher.include_router(payments_router)
    tg_messages_dispatcher.include_router(cover_router)
    # Dependency injection: Settings
    tg_messages_dispatcher[Settings] = settings

    # Core handlers
    setup_handlers(tg_messages_dispatcher, bot, settings)

    await asyncio.gather(
        tg_messages_dispatcher.start_polling(bot, close_bot_session=True),
        start_metrics_server(settings.metrics_host, settings.metrics_port),
    )

def main() -> None:
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    main()
