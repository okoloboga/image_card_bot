import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from utils.formatters import safe_send_message
from keyboards.keyboards import main_menu_keyboard

from aiogram.utils.keyboard import InlineKeyboardBuilder
from database.models import User

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

@router.message(Command("menu"))
async def menu_command(message: Message, db_user: User):
    """
    Shows the main menu with credit balance and a button to buy more.
    """
    builder = InlineKeyboardBuilder()
    builder.button(text="💎 Купить кредиты", callback_data="show_buy_menu")

    text = (
        "<b>Главное меню</b>\n\n"
        f"Ваш баланс: <b>{db_user.credits_remaining}</b> кредитов.\n\n"
        "Используйте кредиты для генерации контента или пополните баланс."
    )
    await safe_send_message(
        message,
        text,
        user_id=message.from_user.id,
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )

@router.callback_query(F.data == "show_main_menu")
async def show_main_menu_callback(callback: CallbackQuery, db_user: User):
    """
    Handles the callback from the main menu button to show the credit menu.
    """
    # Use the existing menu_command logic
    await menu_command(callback.message, db_user)
    await callback.answer() # Acknowledge the callback
