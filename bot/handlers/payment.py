import logging
from typing import Union
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, LabeledPrice, PreCheckoutQuery
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import User
from database.crud import add_credits, get_user, add_referral_earnings
from utils.formatters import safe_send_message

logger = logging.getLogger(__name__)

router = Router()


from keyboards.keyboards import back_to_main_menu_keyboard
...
async def show_buy_credits_menu(event: Union[Message, CallbackQuery], db_user: User):
    """
    Reusable function to show the credit purchase menu.
    Can be triggered by a message or a callback query.
    """
    builder = InlineKeyboardBuilder()
    # payload: buy:credits:{amount}:{price_in_stars}
    builder.button(text="70 Кредитов за 50 ⭐️", callback_data="buy:credits:70:50")
    builder.button(text="160 Кредитов за 100 ⭐️", callback_data="buy:credits:160:100")
    builder.button(text="500 Кредитов за 250 ⭐️", callback_data="buy:credits:500:250")
    builder.button(text="2700 Кредитов за 1000 ⭐️", callback_data="buy:credits:2700:1000")
    builder.button(text="8000 Кредитов за 2500 ⭐️", callback_data="buy:credits:8000:2500")
    builder.button(text="⬅️ Назад в главное меню", callback_data="back_to_main_menu")
    builder.adjust(1)

    text = (
        "<b>💎 Покупка кредитов</b>\n\n"
        "Выберите пакет, который хотите приобрести. Кредиты используются для всех типов генераций.\n\n"
        "• Генерация текста: 1 кредит\n"
        "• Генерация фото: 40 кредитов\n\n"
        f"Ваш текущий баланс: <b>{db_user.credits_remaining}</b> кредитов."
    )

    if isinstance(event, Message):
        await event.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    elif isinstance(event, CallbackQuery):
        # Check if the message content is different before editing
        if event.message and event.message.text != text:
            await event.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
        await event.answer() # Acknowledge the callback

# ============================================================================
# Handlers
# ============================================================================

@router.message(Command("buy_credits"))
async def buy_credits_command(message: Message, db_user: User):
    """
    Shows the credit purchase menu via a command.
    """
    await show_buy_credits_menu(message, db_user)

@router.callback_query(F.data == "show_buy_menu")
async def show_buy_menu_callback(callback: CallbackQuery, db_user: User):
    """
    Shows the credit purchase menu via a callback button.
    """
    await show_buy_credits_menu(callback, db_user)

# ============================================================================
# Отправка инвойса
# ============================================================================

@router.callback_query(F.data.startswith("buy:credits:"))
async def send_invoice_handler(callback: CallbackQuery):
    """
    Создает и отправляет инвойс на основе callback данных.
    """
    try:
        _, type, amount_str, price_str = callback.data.split(":")
        amount = int(amount_str)
        price = int(price_str)
    except (ValueError, IndexError):
        logger.error(f"Invalid callback data for payment: {callback.data}")
        await callback.answer("Произошла ошибка. Попробуйте снова.", show_alert=True)
        return

    if type != "credits":
        logger.error(f"Unknown purchase type in callback: {callback.data}")
        await callback.answer("Неизвестный тип покупки.", show_alert=True)
        return

    title = f"Покупка {amount} кредитов"
    description = f"Пополнение баланса на {amount} кредитов для генерации контента."
    payload = f"buy:credits:{amount}"
    prices = [LabeledPrice(label="кредитов", amount=price)]

    await callback.bot.send_invoice(
        chat_id=callback.from_user.id,
        title=title,
        description=description,
        provider_token="",  # Для Telegram Stars оставляем пустым
        currency="XTR",
        prices=prices,
        payload=payload
    )
    await callback.answer()


# ============================================================================
# Пре-чекаут и успешный платеж
# ============================================================================

@router.pre_checkout_query()
async def pre_checkout_handler(pre_checkout_query: PreCheckoutQuery):
    """
    Подтверждение готовности принять платеж.
    """
    await pre_checkout_query.answer(ok=True)


@router.message(F.successful_payment)
async def success_payment_handler(message: Message, session: AsyncSession, db_user: User, bot: Bot):
    """
    Обработка успешного платежа и начисление реферального бонуса.
    """
    telegram_id = message.from_user.id
    payment_info = message.successful_payment
    payload = payment_info.invoice_payload

    logger.info(f"✅ Successful payment from {telegram_id}. Payload: {payload}, Charge ID: {payment_info.telegram_payment_charge_id}")

    try:
        _, type, amount_str = payload.split(":")
        amount = int(amount_str)
    except (ValueError, IndexError):
        logger.error(f"Invalid payload in successful payment: {payload}")
        await message.answer("Произошла ошибка при зачислении кредитов. Пожалуйста, обратитесь в поддержку.")
        return

    if type == "credits":
        # Начисляем кредиты покупателю
        await add_credits(session, telegram_id, amount)
        success_text = f"🎉 Успешно! Вам начислено {amount} кредитов."
        await message.answer(success_text)

        # --- Логика начисления реферального бонуса ---
        if db_user.referred_by_id:
            referrer = await get_user(session, db_user.referred_by_id)
            if referrer:
                bonus_amount = int(amount * 0.20)
                if bonus_amount > 0:
                    # Начисляем бонус и обновляем статистику
                    await add_credits(session, referrer.telegram_id, bonus_amount)
                    await add_referral_earnings(session, referrer.telegram_id, bonus_amount)
                    
                    logger.info(f"🎁 Awarded {bonus_amount} referral bonus credits to user {referrer.telegram_id}")
                    
                    # Уведомляем реферера
                    try:
                        await bot.send_message(
                            chat_id=referrer.telegram_id,
                            text=f"🎉 Вам начислен реферальный бонус: <b>{bonus_amount}</b> кредитов!\n"
                                 f"Ваш друг (ID: `{telegram_id}`) совершил покупку.",
                            parse_mode="HTML"
                        )
                    except Exception as e:
                        logger.error(f"Failed to send referral bonus notification to {referrer.telegram_id}: {e}")

    else:
        logger.error(f"Unknown purchase type in successful payment payload: {payload}")
        await message.answer("Произошла ошибка при определении типа покупки. Пожалуйста, обратитесь в поддержку.")
        return

