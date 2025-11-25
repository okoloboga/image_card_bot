import logging
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command, CommandObject
from sqlalchemy.ext.asyncio import AsyncSession

from utils.formatters import safe_send_message
from keyboards.keyboards import main_menu_keyboard, back_to_main_menu_keyboard
from aiogram.utils.keyboard import InlineKeyboardBuilder
from database.models import User
from database.crud import get_or_create_user, count_referrals

logger = logging.getLogger(__name__)
router = Router()

@router.message(Command("start"))
async def start_command(message: Message, command: CommandObject, session: AsyncSession, bot: Bot):
    """
    Handles the /start command, including referral links (deep linking).
    """
    referrer_id = None
    if command.args and command.args.startswith("ref_"):
        try:
            referrer_id = int(command.args.split("_")[1])
        except (IndexError, ValueError):
            logger.warning(f"Could not parse referrer_id from args: {command.args}")
            
    db_user = await get_or_create_user(session, message.from_user, referrer_id)

    user_name = message.from_user.first_name
    text = (
        f"Здравствуйте, {user_name}!\n\n"
        "Этот бот — ваш личный помощник в мире контента. Готов помочь с созданием описаний для товаров и улучшением ваших фотографий."
    )

    if db_user.referred_by_id and db_user.credits_remaining == 225:
         text += "\n\n🎉 Поздравляем! Вы получили <b>100 бонусных кредитов</b> за регистрацию по реферальной ссылке."

    await safe_send_message(
        message,
        text,
        user_id=message.from_user.id,
        reply_markup=main_menu_keyboard(),
        parse_mode="HTML"
    )

@router.message(Command("menu"))
async def menu_command(message: Message, db_user: User, session: AsyncSession):
    """
    Shows the main menu with credit balance and a button to buy more.
    """
    builder = InlineKeyboardBuilder()
    builder.button(text="💎 Купить кредиты", callback_data="show_buy_menu")
    builder.button(text="🤝 Реферальная программа", callback_data="show_referral_menu")
    builder.adjust(1)

    # Get referral stats
    referrals_count = await count_referrals(session, db_user.telegram_id)

    text = (
        "<b>Главное меню</b>\n\n"
        f"Ваш баланс: <b>{db_user.credits_remaining}</b> кредитов.\n\n"
        "<b>Реферальная статистика:</b>\n"
        f"• Приглашено пользователей: <b>{referrals_count}</b>\n"
        f"• Заработано с рефералов: <b>{db_user.referral_earnings}</b> кредитов\n\n"
        "Используйте кредиты для генерации контента или пополните баланс."
    )
    
    # Check if it's a callback, then edit the message
    if isinstance(message, CallbackQuery):
        await message.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    else:
        await safe_send_message(
            message,
            text,
            user_id=message.from_user.id,
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )

@router.message(Command("support"))
async def support_command(message: Message):
    """
    Handles the /support command.
    """
    text = (
        "<b>Поддержка</b>\n\n"
        "Если у вас возникли проблемы или есть вопросы, "
        "пожалуйста, свяжитесь с нашей службой поддержки.\n\n"
        "Контакт: @Tsarevich_Asgardsky_Official"
    )
    await safe_send_message(
        message,
        text,
        user_id=message.from_user.id,
        parse_mode="HTML"
    )

@router.message(Command("referral"))
async def referral_command(message: Message, db_user: User, bot: Bot, session: AsyncSession):
    """
    Generates and shows the user's referral link.
    """
    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ Назад в главное меню", callback_data="back_to_main_menu")

    if not db_user.referral_link:
        # Generate and save referral link if it doesn't exist
        db_user.referral_link = f"ref_{db_user.telegram_id}"
        await session.commit()

    bot_info = await bot.get_me()
    link = f"https://t.me/{bot_info.username}?start={db_user.referral_link}"

    text = (
        "<b>🤝 Ваша реферальная ссылка</b>\n\n"
        "Приглашайте друзей и получайте бонусы!\n\n"
        "<b>Что вы получаете:</b>\n"
        "• <b>20%</b> в кредитах от каждого пополнения вашего друга.\n\n"
        "<b>Что получает ваш друг:</b>\n"
        "• <b>+100</b> бонусных кредитов при регистрации.\n\n"
        "Ваша ссылка для приглашения:\n"
        f"<code>{link}</code>"
    )
    
    # Check if it's a callback, then edit the message
    if isinstance(message, CallbackQuery):
        await message.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML", disable_web_page_preview=True)
    else:
        await safe_send_message(
            message,
            text,
            user_id=message.from_user.id,
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
            disable_web_page_preview=True
        )

@router.callback_query(F.data == "show_referral_menu")
async def show_referral_menu_callback(callback: CallbackQuery, db_user: User, bot: Bot, session: AsyncSession):
    """
    Handles the callback from the menu button to show the referral program info.
    """
    await referral_command(callback, db_user, bot, session)
    await callback.answer()

@router.callback_query(F.data == "show_main_menu")
async def show_main_menu_callback(callback: CallbackQuery, db_user: User, session: AsyncSession):
    """
    Handles the callback from the main menu button to show the credit menu.
    """
    await menu_command(callback, db_user, session)
    await callback.answer()

@router.callback_query(F.data == "back_to_main_menu")
async def back_to_main_menu_callback(callback: CallbackQuery, db_user: User, session: AsyncSession):
    """
    Handles the 'back to main menu' button.
    """
    await menu_command(callback, db_user, session)
    await callback.answer()
