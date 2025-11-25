import logging
from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command
from utils.formatters import safe_send_message
from keyboards.keyboards import main_menu_keyboard

logger = logging.getLogger(__name__)
router = Router()

@router.message(Command("start"))
async def start_command(message: Message):
    """
    Handles the /start command.
    """
    user_name = message.from_user.first_name
    text = (
        f"Здравствуйте, {user_name}!\n\n"
        "Этот бот — ваш личный помощник в мире контента. Готов помочь с созданием описаний для товаров и улучшением ваших фотографий."
    )
    await safe_send_message(
        message,
        text,
        user_id=message.from_user.id,
        reply_markup=main_menu_keyboard()
    )
