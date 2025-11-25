# bot/database/engine.py

import os
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from .models import Base

# DB_URL will be like "sqlite+aiosqlite:///path/to/bot.db"
# We place the DB in the project root.
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "bot.db")
DB_URL = f"sqlite+aiosqlite:///{DB_PATH}"

class Database:
    def __init__(self, db_url: str = DB_URL):
        self.engine = create_async_engine(db_url)
        self.session_maker = async_sessionmaker(
            bind=self.engine,
            class_=AsyncSession,
            expire_on_commit=False
        )

    async def get_session(self) -> AsyncSession:
        """Provides a database session."""
        async with self.session_maker() as session:
            yield session

    async def init_db(self):
        """Initializes the database and creates tables."""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

db = Database()

# Dependency for FastAPI-like session management in handlers/middleware
async def get_db_session() -> AsyncSession:
    async for session in db.get_session():
        yield session
