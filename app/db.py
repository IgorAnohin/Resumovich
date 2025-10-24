from __future__ import annotations
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from typing import Optional
import asyncio

_client: Optional[AsyncIOMotorClient] = None
_db: Optional[AsyncIOMotorDatabase] = None

async def init_db(dsn: str, db_name: str) -> AsyncIOMotorDatabase:
    global _client, _db
    _client = AsyncIOMotorClient(dsn)
    _db = _client.get_database(db_name)

    await _db.users.create_index("tg_user_id", unique=True)
    await _db.messages.create_index([("message_id", 1), ("chat_id", 1)])
    await _db.analyses.create_index([("user_id", 1), ("created_at", -1)])
    return _db

def db() -> AsyncIOMotorDatabase:
    assert _db is not None, "DB не инициализирована"
    return _db
