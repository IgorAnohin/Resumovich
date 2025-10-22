from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict, Any, List

@dataclass
class User:
    tg_user_id: int
    tg_chat_id: int
    name: str
    accepted_rules: bool = False
    plan: str = "FREE"
    subscription_until: Optional[datetime] = None
    one_time_full_left: int = 1
    cover_packs_left: int = 0
    hr_reviews_left: int = 0

@dataclass
class Analysis:
    user_id: int
    file_path: str
    filename: str
    score: int
    mode: str  # "score_only" | "full"
    payload: Dict[str, Any]
