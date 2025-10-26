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
    COMMAND = "command"
    BOT_ANSWER = "bot_answer"


class User(BaseModel):
    tg_user_id: int
    tg_chat_id: int
    name: str
    accepted_rules: bool = False
    subscription_until: datetime
    one_time_full_left: int = 1
    cover_packs_left: int = 0
    hr_reviews_left: int = 0
    created_at: datetime = Field(..., default_factory=datetime.now)
    updated_at: Optional[datetime] = None

class AnalysisDetail(BaseModel):
    score: int
    strengths: list[str]
    problems: list[str]
    actions: list[str]
    sections: Dict[str, Any]
    ok: bool
    raw: str
    prompt: str


class Analysis(BaseModel):
    user_id: int
    filepaths: list[str]
    details: list[AnalysisDetail]
    created_at: datetime = Field(..., default_factory=datetime.now)


class CheckFileResult(BaseModel):
    is_valid: bool
    reason: str


class FileChecking(BaseModel):
    user_id: int
    filepath: str
    result: CheckFileResult
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

