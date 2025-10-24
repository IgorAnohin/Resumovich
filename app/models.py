from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, Dict, Any

class Plans(StrEnum):
    FREE = "FREE"
    PRO = "PRO"

class Mode(StrEnum):
    SCORE_ONLY = "score_only"
    FULL = "full"

class MessageType(StrEnum):
    CALLBACK = "callback"
    DOCUMENT = "document"
    TEXT = "text"
    BOT_ANSWER = "bot_answer"


class User(BaseModel):
    tg_user_id: int
    tg_chat_id: int
    name: str
    subscription_until: datetime
    created_at: datetime = Field(..., default_factory=datetime.now)
    accepted_rules: bool = False
    plan: Plans = Plans.FREE
    one_time_full_left: int = 1
    cover_packs_left: int = 0
    hr_reviews_left: int = 0
    updated_at: Optional[datetime] = None

class AnalysisDetail(BaseModel):
    score: int
    strengths: list[str]
    problems: list[str]
    actions: list[str]
    sections: Dict[str, Any]
    ok: bool
    raw: str


class Analysis(BaseModel):
    user_id: int
    filename: str
    mode: Mode  # "score_only" | "full"
    details: list[AnalysisDetail]
    created_at: datetime = Field(..., default_factory=datetime.now)


class MessageModel(BaseModel):
    type: MessageType
    message_id: int
    text: str
    chat_id: int
    user_id: int
    callback_data: Optional[Any] = None
    file_name: Optional[str] = None
    created_at: datetime = Field(..., default_factory=datetime.now)
