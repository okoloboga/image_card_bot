"""
Card Generation Handler - генерация карточек товаров через GPT.

Кнопка:
- 🎨 Генерация карточки (в меню AI-помощник)
"""

import logging
import os
import re
from typing import Optional, Dict, Any
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import StateFilter, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
import aiohttp

from core.config import config
from core.states import CardGenerationStates
from keyboards.keyboards import main_menu_keyboard, create_card_generation_keyboard
from utils.formatters import (
    safe_send_message,
    handle_telegram_errors,
)

logger = logging.getLogger(__name__)

router = Router()

# URL GPT Service
GPT_SERVICE_URL = getattr(config, "gpt_service_url", None) or os.getenv("GPT_SERVICE_URL", "http://gpt:9000")


# ============================================================================
# Callback start_card_generation - начать генерацию карточки
# ============================================================================

@router.callback_query(F.data == "start_card_generation")
@handle_telegram_errors
async def callback_start_card_generation(callback: CallbackQuery, state: FSMContext):
    """Начать процесс генерации карточки товара."""
    telegram_id = callback.from_user.id
    
    logger.info(f"🎨 User {telegram_id} started card generation")
    
    # Инициализируем данные в FSM
    await state.update_data(
        photo_file_id=None,
        characteristics={},
        target_audience=None,
        selling_points=None,
        semantic_core_text=None,
    )
    
    await state.set_state(CardGenerationStates.waiting_for_photo)
    
    welcome_text = (
        "✍️ <b>Создание описания для товара</b>\n\n"
        "Давайте вместе подготовим продающий текст для вашего товара.\n\n"
        "<b>Шаг 1 из 4:</b> Загрузите основное изображение товара."
    )
    
    await callback.message.edit_text(
        welcome_text,
        parse_mode="HTML",
        reply_markup=create_card_generation_keyboard()
    )
    await callback.answer()


# ============================================================================
# Обработка фото
# ============================================================================

@router.message(StateFilter(CardGenerationStates.waiting_for_photo), F.photo)
@handle_telegram_errors
async def process_card_photo(message: Message, state: FSMContext):
    """Обработка фото товара."""
    telegram_id = message.from_user.id
    photo = message.photo[-1]
    
    logger.info(f"📸 Photo received from user {telegram_id}, file_id: {photo.file_id}")
    
    await state.update_data(
        photo_file_id=photo.file_id,
        characteristics={},
        characteristics_step="name"
    )
    
    await state.set_state(CardGenerationStates.waiting_for_characteristics)
    
    await safe_send_message(
        message,
        "🖼️ <b>Изображение принято.</b>\n\n"
        "<b>Шаг 2 из 4:</b> Теперь укажите основные данные о товаре.\n\n"
        "Начнем с <b>названия</b>. Как называется ваш товар?",
        user_id=telegram_id,
        parse_mode="HTML",
        reply_markup=create_card_generation_keyboard()
    )


@router.message(StateFilter(CardGenerationStates.waiting_for_photo))
@handle_telegram_errors
async def process_card_photo_error(message: Message, state: FSMContext):
    """Обработка некорректного ввода (не фото)."""
    telegram_id = message.from_user.id
    
    await safe_send_message(
        message,
        "❗️ Ожидается изображение. Пожалуйста, отправьте фотографию вашего товара.",
        user_id=telegram_id,
        parse_mode="HTML"
    )


# ============================================================================
# Обработка характеристик
# ============================================================================

@router.message(StateFilter(CardGenerationStates.waiting_for_characteristics), F.text)
@handle_telegram_errors
async def process_characteristics(message: Message, state: FSMContext):
    """Обработка ключевых характеристик - поочередно запрашиваем каждое поле."""
    telegram_id = message.from_user.id
    text = message.text.strip()
    
    data = await state.get_data()
    characteristics = data.get("characteristics", {})
    current_step = data.get("characteristics_step", "name")
    
    if current_step == "name":
        characteristics["name"] = text
        await state.update_data(characteristics=characteristics, characteristics_step="brand")
        
        await safe_send_message(
            message,
            f"👍 <b>Название принято:</b> {text}\n\n"
            f"Теперь введите <b>бренд</b>.",
            user_id=telegram_id,
            parse_mode="HTML",
            reply_markup=create_card_generation_keyboard()
        )
    
    elif current_step == "brand":
        characteristics["brand"] = text
        await state.update_data(characteristics=characteristics, characteristics_step="category")
        
        await safe_send_message(
            message,
            f"👍 <b>Бренд сохранен:</b> {text}\n\n"
            f"К какой <b>категории</b> относится товар?",
            user_id=telegram_id,
            parse_mode="HTML",
            reply_markup=create_card_generation_keyboard()
        )
    
    elif current_step == "category":
        characteristics["category"] = text
        await state.update_data(characteristics=characteristics)
        
        await state.set_state(CardGenerationStates.waiting_for_audience)
        
        await safe_send_message(
            message,
            f"👍 <b>Все данные записаны.</b>\n\n"
            f"<b>Шаг 3 из 4:</b> Опишите вашу целевую аудиторию.\n\n"
            f"<i>Например: молодые мамы, геймеры, любители активного отдыха.</i>",
            user_id=telegram_id,
            parse_mode="HTML",
            reply_markup=create_card_generation_keyboard()
        )


@router.message(StateFilter(CardGenerationStates.waiting_for_characteristics))
@handle_telegram_errors
async def process_characteristics_error(message: Message, state: FSMContext):
    """Обработка некорректного ввода в состоянии ожидания характеристик (не текст)."""
    telegram_id = message.from_user.id
    
    data = await state.get_data()
    current_step = data.get("characteristics_step", "name")
    
    field_names = {
        "name": "название товара",
        "brand": "бренд",
        "category": "категорию"
    }
    field_name = field_names.get(current_step, "данные")
    
    await safe_send_message(
        message,
        f"❗️ Требуется текстовое описание. Пожалуйста, введите {field_name}.",
        user_id=telegram_id,
        parse_mode="HTML"
    )

# ============================================================================
# Обработка целевой аудитории
# ============================================================================

@router.message(StateFilter(CardGenerationStates.waiting_for_audience), F.text)
@handle_telegram_errors
async def process_target_audience(message: Message, state: FSMContext):
    """Обработка описания целевой аудитории."""
    telegram_id = message.from_user.id
    audience_text = message.text
    
    logger.info(f"👥 Target audience received from user {telegram_id}")
    
    await state.update_data(target_audience=audience_text)
    await state.set_state(CardGenerationStates.waiting_for_selling_points)
    
    await safe_send_message(
        message,
        "👍 <b>Аудитория определена.</b>\n\n"
        "<b>Шаг 4 из 4:</b> Перечислите главные достоинства или уникальные особенности вашего товара.\n\n"
        "<i>Например: ручная работа, водонепроницаемый, гипоаллергенный материал.</i>",
        user_id=telegram_id,
        parse_mode="HTML",
        reply_markup=create_card_generation_keyboard()
    )


@router.message(StateFilter(CardGenerationStates.waiting_for_audience))
@handle_telegram_errors
async def process_target_audience_error(message: Message, state: FSMContext):
    """Обработка некорректного ввода в состоянии ожидания целевой аудитории (не текст)."""
    telegram_id = message.from_user.id
    
    await safe_send_message(
        message,
        "❗️ Ожидается текстовое описание. Расскажите о вашей целевой аудитории.",
        user_id=telegram_id,
        parse_mode="HTML"
    )


from sqlalchemy.ext.asyncio import AsyncSession
from database.models import User
from database.crud import use_credits

# Стоимость операций
CARD_GENERATION_COST = 1

# ============================================================================
# Обработка selling points
# ============================================================================

@router.message(StateFilter(CardGenerationStates.waiting_for_selling_points), F.text)
@handle_telegram_errors
async def process_selling_points(message: Message, state: FSMContext, session: AsyncSession, db_user: User):
    """Обработка selling points и запуск генерации."""
    telegram_id = message.from_user.id
    selling_points_text = message.text
    
    logger.info(f"⭐ Selling points received from user {telegram_id}")
    
    await state.update_data(selling_points=selling_points_text)
    
    await generate_card_with_gpt(message, state, session, db_user)


@router.message(StateFilter(CardGenerationStates.waiting_for_selling_points))
@handle_telegram_errors
async def process_selling_points_error(message: Message, state: FSMContext):
    """Обработка некорректного ввода в состоянии ожидания selling points (не текст)."""
    telegram_id = message.from_user.id
    
    await safe_send_message(
        message,
        "❗️ Ожидается текстовое описание. Укажите ключевые преимущества товара.",
        user_id=telegram_id,
        parse_mode="HTML"
    )

# ============================================================================
# Генерация карточки через GPT
# ============================================================================

async def generate_card_with_gpt(message: Message, state: FSMContext, session: AsyncSession, db_user: User):
    """Отправка данных в GPT сервис для генерации карточки."""
    telegram_id = message.from_user.id

    # 1. Проверка кредитов
    if db_user.credits_remaining < CARD_GENERATION_COST:
        logger.info(f"🚫 User {telegram_id} has not enough credits for card generation.")
        await safe_send_message(
            message,
            f"У вас недостаточно кредитов для генерации описания (нужно {CARD_GENERATION_COST}, у вас {db_user.credits_remaining}).\n"
            "Чтобы пополнить баланс, воспользуйтесь командой /buy_credits.",
            user_id=telegram_id
        )
        await state.clear()
        return

    data = await state.get_data()
    
    photo_file_id = data.get("photo_file_id")
    characteristics = data.get("characteristics", {})
    target_audience = data.get("target_audience")
    selling_points = data.get("selling_points")
    
    if not photo_file_id or not all([characteristics.get("name"), characteristics.get("brand"), characteristics.get("category")]):
        await safe_send_message(
            message,
            "⚠️ Обнаружена нехватка данных. Пожалуйста, начните процесс заново.",
            user_id=telegram_id
        )
        await state.clear()
        return
    
    processing_message = await safe_send_message(
        message,
        f"🤖 <b>Начинаю генерацию текста...</b>\n\n"
        f"Это будет стоить {CARD_GENERATION_COST} кредит. Ваш баланс: {db_user.credits_remaining - CARD_GENERATION_COST}\n"
        "Это может занять до двух минут. Пожалуйста, подождите.",
        user_id=telegram_id,
        parse_mode="HTML"
    )
    
    endpoint = f"{GPT_SERVICE_URL.rstrip('/')}/v1/card/generate"
    payload = {
        "telegram_id": telegram_id,
        "photo_file_id": photo_file_id,
        "characteristics": characteristics,
        "target_audience": target_audience,
        "selling_points": selling_points,
        "semantic_core_text": None,
    }
    headers = {
        "Content-Type": "application/json",
        "X-API-KEY": config.api_secret_key
    }
    
    try:
        # Списываем кредит ПЕРЕД запросом
        await use_credits(session, telegram_id, CARD_GENERATION_COST)
        logger.info(f"💳 {CARD_GENERATION_COST} credit(s) used by user {telegram_id}. Remaining: {db_user.credits_remaining}")

        timeout = aiohttp.ClientTimeout(total=120)
        async with aiohttp.ClientSession(timeout=timeout) as aio_session:
            async with aio_session.post(endpoint, json=payload, headers=headers) as resp:
                
                if resp.status == 200:
                    result = await resp.json()
                    card_text = result.get("card", "")
                    
                    if card_text.startswith("ERROR:"):
                        error_msg = card_text.replace("ERROR:", "").strip()
                        if "not available in your region" in error_msg.lower() or "unsupported_country" in error_msg.lower():
                            await safe_send_message(
                                message,
                                "🚫 <b>Сервис недоступен в вашем регионе.</b>\n\n"
                                "Для решения проблемы, пожалуйста, свяжитесь с администратором.",
                                user_id=telegram_id,
                                parse_mode="HTML"
                            )
                        else:
                            await safe_send_message(
                                message,
                                f"❗️ <b>При генерации произошла ошибка:</b>\n\n{error_msg}",
                                user_id=telegram_id,
                                parse_mode="HTML"
                            )
                    else:
                        await safe_send_message(
                            message,
                            f"🎉 <b>Ваше описание готово!</b>\n\n{card_text}",
                            user_id=telegram_id,
                            parse_mode="HTML"
                        )
                else:
                    error_body = await resp.text()
                    logger.error(f"❌ GPT Service error {resp.status}: {error_body}")
                    await safe_send_message(
                        message,
                        "❗️ <b>Сервис генерации временно недоступен.</b>\n"
                        "Пожалуйста, попробуйте снова через некоторое время.",
                        user_id=telegram_id
                    )
                
                await state.clear()
                
                await safe_send_message(
                    message,
                    "Что вы хотите сделать дальше?",
                    user_id=telegram_id,
                    parse_mode="HTML",
                    reply_markup=main_menu_keyboard()
                )
    
    except aiohttp.ClientError as e:
        logger.error(f"❌ Network error calling GPT Service: {e}")
        await safe_send_message(
            message,
            "❗️ Не удалось подключиться к сервису генерации. Пожалуйста, попробуйте позже.",
            user_id=telegram_id
        )
        await state.clear()
    
    except Exception as e:
        logger.error(f"❌ Unexpected error in card generation: {e}", exc_info=True)
        await safe_send_message(
            message,
            "❗️ Произошла внутренняя ошибка. Мы уже работаем над ее устранением.",
            user_id=telegram_id
        )
        await state.clear()
    finally:
        if processing_message:
            await processing_message.delete()


# ============================================================================
# Callback cancel_card_generation - отмена генерации
# ============================================================================

@router.callback_query(F.data == "cancel_card_generation")
@handle_telegram_errors
async def callback_cancel_card_generation(callback: CallbackQuery, state: FSMContext):
    """Отменить процесс генерации карточки."""
    telegram_id = callback.from_user.id
    
    logger.info(f"🔚 User {telegram_id} cancelled card generation")
    
    await state.clear()
    
    await callback.message.edit_text(
        "Операция отменена. Вы вернулись в главное меню.",
        reply_markup=main_menu_keyboard()
    )
    
    await callback.answer()

