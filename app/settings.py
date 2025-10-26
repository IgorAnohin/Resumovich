from __future__ import annotations
import os
from pydantic import BaseModel
from pydantic_settings import SettingsConfigDict, BaseSettings


class LLMSettings(BaseModel):
    base_url: str
    api_key: str
    general_model: str
    small_model: str


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_nested_delimiter='__')

    telegram_token: str
    mongo_dsn: str = "mongodb://localhost:27017/resume_bot"
    db_name: str = "resume_bot"
    data_dir: str = "/data/uploads"
    free_one_time_full: int = 1
    sentry_dsn: str | None
    user_agreement_url: str | None
    privacy_url: str | None
    # llm_settings: LLMSettings | None = None
    payments_provider_token: str | None = None
    llm_settings: LLMSettings


def get_settings() -> Settings:
    return Settings()
