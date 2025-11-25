import asyncio
import logging
import os
import sys
from pathlib import Path
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
import uvicorn

# Добавляем путь к модулям бота
sys.path.insert(0, str(Path(__file__).parent))

from core.config import config
from database.engine import db
from middleware.db import DbSessionMiddleware
from middleware.error_handler import ErrorHandlerMiddleware, LoggingMiddleware, RateLimitMiddleware
from handlers.commands import router as commands_router
from handlers.card_generation import router as card_generation_router
from handlers.photo_processing import router as photo_processing_router
from handlers.payment import router as payment_router

# Настройка логирования
logging.basicConfig(
    level=getattr(logging, config.log_level.upper()),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def on_startup(dispatcher: Dispatcher):
    """Действия при старте бота."""
    logger.info("Initializing database...")
    await db.init_db()
    logger.info("Database initialized.")

bot = Bot(token=config.bot_token)
dp = Dispatcher()

# Регистрируем on_startup
dp.startup.register(on_startup)

# Подключаем middleware
# Важно: DbSessionMiddleware должен идти до других, которые могут использовать сессию
dp.message.middleware(DbSessionMiddleware(session_pool=db.session_maker))
dp.callback_query.middleware(DbSessionMiddleware(session_pool=db.session_maker))

dp.message.middleware(ErrorHandlerMiddleware())
dp.callback_query.middleware(ErrorHandlerMiddleware())
dp.message.middleware(LoggingMiddleware())
dp.callback_query.middleware(LoggingMiddleware())
dp.message.middleware(RateLimitMiddleware())
dp.callback_query.middleware(RateLimitMiddleware())

# Подключаем роутеры
dp.include_router(commands_router)
dp.include_router(card_generation_router)
dp.include_router(photo_processing_router)
dp.include_router(payment_router)

async def main():
    logger.info("Bot started...")
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())