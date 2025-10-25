from aiogram import Dispatcher, F, Bot

from app.telegram.handlers.analysis import analysis_router
from app.telegram.handlers.fallback import fallback_router
from app.telegram.handlers.start import start_router
from app.telegram.handlers.subscription import subscription_router


def setup_routes(dp: Dispatcher) -> None:

    # dp.update.middleware(CommandsSyncMiddleware())

    dp.include_router(start_router)
    dp.include_router(analysis_router)
    dp.include_router(subscription_router)

    # Fallback must be the last router
    dp.include_router(fallback_router)
