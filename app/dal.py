from datetime import datetime, timedelta
from typing import Any, Dict

from aiogram.types import Message
from bson import ObjectId

from .db import db
from .models import User, Analysis, MessageModel

class UserNotFound(Exception):
    pass

class UsersDAL:
    @classmethod
    async def ensure_user_from_message(cls, message: Message) -> User:
        try:
            return await cls.get_user(message.from_user.id)
        except UserNotFound:
            name = f"{message.from_user.first_name} {message.from_user.last_name}"
            # One-time free value can be set via environment by app initialization; keep default here
            return await cls._create_user(message.from_user.id, message.chat.id, name)

    @staticmethod
    async def get_user(tg_user_id: int) -> User:
        doc = await db().users.find_one({"tg_user_id": tg_user_id})
        if not doc:
            raise UserNotFound("User not found")
        return User.model_validate(doc)

    @staticmethod
    async def _create_user(tg_user_id: int, tg_chat_id: int, name: str) -> User:
        user = User(
            tg_user_id=tg_user_id,
            tg_chat_id=tg_chat_id,
            name=name,
            subscription_until=datetime.utcnow() + timedelta(days=3),
        )
        await db().users.insert_one(user.model_dump())
        return user

    @staticmethod
    async def accept_rules(user_id: int) -> None:
        await db().users.update_one(
            {"tg_user_id": user_id},
            {"$set": {"accepted_rules": True, "updated_at": datetime.utcnow()}},
        )


    @staticmethod
    async def consume_one_time_full(tg_user_id: int) -> bool:
        res = await db().users.update_one(
            {"tg_user_id": tg_user_id},
            {"$inc": {"one_time_full_left": -1}},
        )
        return bool(res.modified_count)

    @staticmethod
    async def set_subscription_until(tg_user_id: int, until: datetime) -> None:
        await db().users.update_one(
            {"tg_user_id": tg_user_id},
            {"$set": {"subscription_until": until, "updated_at": datetime.utcnow()}},
        )


class MessagesDAL:
    @staticmethod
    async def insert(data: MessageModel) -> Any:
        res = await db().messages.insert_one(data.model_dump())
        return res.inserted_id

class AnalyticsDAL:
    @staticmethod
    async def insert(data: Analysis) -> ObjectId:
        res = await db().analyses.insert_one(data.model_dump())
        return res.inserted_id

    @staticmethod
    async def update_analysis(analysis_id: Any, fields: Dict[str, Any]) -> None:
        if not isinstance(analysis_id, ObjectId):
            try:
                analysis_id = ObjectId(str(analysis_id))
            except Exception:
                pass
        await db().analyses.update_one({"_id": analysis_id}, {"$set": fields})
