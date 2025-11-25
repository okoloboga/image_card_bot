# bot/middleware/db.py

from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, User
from sqlalchemy.ext.asyncio import async_sessionmaker

from database.crud import get_or_create_user

class DbSessionMiddleware(BaseMiddleware):
    def __init__(self, session_pool: async_sessionmaker):
        super().__init__()
        self.session_pool = session_pool

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        # Aiogram's context middleware populates 'event_from_user'
        user: User | None = data.get("event_from_user")

        # If the event is not associated with a user, just continue
        if not user:
            return await handler(event, data)
            
        async with self.session_pool() as session:
            data["session"] = session
            
            # Get or create user from the database and pass it to the handler
            db_user = await get_or_create_user(session, user)
            data["db_user"] = db_user
            
            result = await handler(event, data)
        
        return result
