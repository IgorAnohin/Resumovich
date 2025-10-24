from __future__ import annotations
import os
from pydantic import BaseModel

class Settings(BaseModel):
    telegram_token: str
    mongo_dsn: str
    db_name: str
    data_dir: str
    sentry_dsn: str | None
    user_agreement_url: str | None
    privacy_url: str | None
    free_one_time_full: int
    llm_base_url: str | None
    llm_api_key: str | None
    llm_model_name: str | None
    callback_data: str = "ACCEPT_RULES"


def get_settings() -> Settings:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN не задан")
    return Settings(
        telegram_token=token,
        mongo_dsn=os.environ.get("MONGO_DSN", "mongodb://localhost:27017/resume_bot"),
        db_name=os.environ.get("DB_NAME", "resume_bot"),
        data_dir=os.environ.get("DATA_DIR", "/data/uploads"),
        sentry_dsn=os.environ.get("SENTRY_DSN") or None,
        user_agreement_url=os.environ.get("USER_AGREEMENT_URL") or None,
        privacy_url=os.environ.get("PRIVACY_URL") or None,
        free_one_time_full=int(os.environ.get("FREE_ONE_TIME_FULL", "1")),
        llm_base_url=os.environ.get("LLM_BASE_URL"),
        llm_api_key=os.environ.get("LLM_API_KEY"),
        llm_model_name=os.environ.get("LLM_MODEL_NAME"),
    )
