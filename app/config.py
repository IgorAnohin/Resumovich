from __future__ import annotations
import os
from dataclasses import dataclass

@dataclass(frozen=True)
class Settings:
    telegram_token: str
    mongo_dsn: str
    db_name: str
    data_dir: str
    sentry_dsn: str | None
    metrics_host: str
    metrics_port: int
    user_agreement_url: str | None
    privacy_url: str | None
    free_one_time_full: int
    pro_days_on_payment: int
    payments_provider_token: str | None
    pro_price_rub: int
    hr_review_price_rub: int
    cover_pack_price_rub: int
    llm_base_url: str | None
    llm_api_key: str | None
    llm_model_name: str | None

def get_settings() -> Settings:
    token = os.environ.get("TELEGRAM_BOT_TOKEN") or ""
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN не задан")
    return Settings(
        telegram_token=token,
        mongo_dsn=os.environ.get("MONGO_DSN", "mongodb://localhost:27017/resume_bot"),
        db_name=os.environ.get("DB_NAME", "resume_bot"),
        data_dir=os.environ.get("DATA_DIR", "/data/uploads"),
        sentry_dsn=os.environ.get("SENTRY_DSN") or None,
        metrics_host=os.environ.get("METRICS_HOST", "0.0.0.0"),
        metrics_port=int(os.environ.get("METRICS_PORT", "8000")),
        user_agreement_url=os.environ.get("USER_AGREEMENT_URL") or None,
        privacy_url=os.environ.get("PRIVACY_URL") or None,
        free_one_time_full=int(os.environ.get("FREE_ONE_TIME_FULL", "1")),
        pro_days_on_payment=int(os.environ.get("PRO_DAYS_ON_PAYMENT", "30")),
        payments_provider_token=os.environ.get("PAYMENTS_PROVIDER_TOKEN") or None,
        pro_price_rub=int(os.environ.get("PRO_PRICE_RUB", "29900")),
        hr_review_price_rub=int(os.environ.get("HR_REVIEW_PRICE_RUB", "149900")),
        cover_pack_price_rub=int(os.environ.get("COVER_PACK_PRICE_RUB", "7900")),
        llm_base_url=os.environ.get("LLM_BASE_URL") or None,
        llm_api_key=os.environ.get("LLM_API_KEY") or None,
        llm_model_name=os.environ.get("LLM_MODEL_NAME") or None,
    )
