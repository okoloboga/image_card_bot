"""
Photo Processing Handler - обработка фотографий через нейронную сеть.

Кнопка:
- 📸 Обработка фото (в меню AI-помощник)
"""

import logging
import os
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import StateFilter, CommandStart
from aiogram.fsm.context import FSMContext
import aiohttp

from core.config import config
from core.states import PhotoProcessingStates
from keyboards.keyboards import main_menu_keyboard, create_photo_processing_keyboard
from utils.formatters import (
    safe_send_message,
    handle_telegram_errors,
)

logger = logging.getLogger(__name__)

router = Router()

# URL GPT Service
GPT_SERVICE_URL = getattr(config, "gpt_service_url", None) or os.getenv("GPT_SERVICE_URL", "http://gpt:9000")


# ============================================================================
# Callback start_photo_processing - начать обработку фото
# ============================================================================

@router.callback_query(F.data == "start_photo_processing")
@handle_telegram_errors
async def callback_start_photo_processing(callback: CallbackQuery, state: FSMContext):
    """Начать процесс обработки фотографии."""
    telegram_id = callback.from_user.id
    
    logger.info(f"📸 User {telegram_id} started photo processing")
    
    await state.update_data(photo_file_id=None, prompt=None)
    
    await state.set_state(PhotoProcessingStates.waiting_for_photo)
    
    welcome_text = (
        "🖼️ <b>Мастерская изображений</b>\n\n"
        "Готов преобразить ваше фото! Просто отправьте его мне.\n\n"
        "<b>Этап 1:</b> Жду ваше изображение."
    )
    
    await callback.message.edit_text(
        welcome_text,
        parse_mode="HTML",
        reply_markup=create_photo_processing_keyboard()
    )
    await callback.answer()


# ============================================================================
# Обработка фото
# ============================================================================

@router.message(StateFilter(PhotoProcessingStates.waiting_for_photo), F.photo)
@handle_telegram_errors
async def process_photo(message: Message, state: FSMContext):
    """Обработка фото от пользователя."""
    telegram_id = message.from_user.id
    photo = message.photo[-1]
    
    logger.info(f"📸 Photo received from user {telegram_id}, file_id: {photo.file_id}")
    
    await state.update_data(photo_file_id=photo.file_id)
    
    await state.set_state(PhotoProcessingStates.waiting_for_prompt)
    
    await safe_send_message(
        message,
        "✨ <b>Отличное фото!</b>\n\n"
        "<b>Этап 2:</b> Теперь расскажите, что бы вы хотели с ним сделать?\n\n"
        "<i>Например: «убери фон», «сделай в стиле аниме», «добавь солнечных лучей».</i>",
        user_id=telegram_id,
        parse_mode="HTML",
        reply_markup=create_photo_processing_keyboard()
    )


@router.message(StateFilter(PhotoProcessingStates.waiting_for_photo))
@handle_telegram_errors
async def process_photo_error(message: Message, state: FSMContext):
    """Обработка некорректного ввода (не фото)."""
    telegram_id = message.from_user.id
    
    await safe_send_message(
        message,
        "Это не похоже на фото. Пожалуйста, отправьте изображение.",
        user_id=telegram_id,
        parse_mode="HTML"
    )


# ============================================================================
# Обработка промпта
# ============================================================================

@router.message(StateFilter(PhotoProcessingStates.waiting_for_prompt), F.text)
@handle_telegram_errors
async def process_prompt(message: Message, state: FSMContext):
    """Обработка текстового описания (промпта)."""
    telegram_id = message.from_user.id
    prompt_text = message.text.strip()
    
    if len(prompt_text) < 5:
        await safe_send_message(
            message,
            "Слишком короткое описание. Попробуйте рассказать подробнее, что нужно сделать.",
            user_id=telegram_id,
            parse_mode="HTML"
        )
        return
    
    if len(prompt_text) > 1500:
        await safe_send_message(
            message,
            "Ваше описание слишком длинное. Пожалуйста, будьте лаконичнее (до 1500 символов).",
            user_id=telegram_id,
            parse_mode="HTML"
        )
        return
    
    logger.info(f"📝 Prompt received from user {telegram_id}: {prompt_text[:50]}...")
    
    await state.update_data(prompt=prompt_text)
    
    await process_photo_with_api(message, state)


@router.message(StateFilter(PhotoProcessingStates.waiting_for_prompt))
@handle_telegram_errors
async def process_prompt_error(message: Message, state: FSMContext):
    """Обработка некорректного ввода в состоянии ожидания промпта (не текст)."""
    telegram_id = message.from_user.id
    
    await safe_send_message(
        message,
        "Я ожидаю текстовое описание. Расскажите, как мне изменить ваше фото?",
        user_id=telegram_id,
        parse_mode="HTML"
    )

# ============================================================================
# Обработка фото через API
# ============================================================================

async def process_photo_with_api(message: Message, state: FSMContext):
    """Отправка данных в GPT сервис для обработки фото."""
    telegram_id = message.from_user.id
    
    data = await state.get_data()
    
    photo_file_id = data.get("photo_file_id")
    prompt = data.get("prompt")
    
    if not photo_file_id or not prompt:
        await safe_send_message(
            message,
            "Что-то пошло не так, не хватает данных. Давайте начнем сначала.",
            user_id=telegram_id
        )
        await state.clear()
        return
    
    await safe_send_message(
        message,
        "🔮 <b>Колдую над вашим изображением...</b>\n\n"
        "Обычно это занимает не больше минуты.",
        user_id=telegram_id,
        parse_mode="HTML"
    )
    
    endpoint = f"{GPT_SERVICE_URL.rstrip('/')}/v1/photo/process"
    payload = {
        "telegram_id": telegram_id,
        "photo_file_id": photo_file_id,
        "prompt": prompt
    }
    headers = {
        "Content-Type": "application/json",
        "X-API-KEY": config.api_secret_key
    }
    
    try:
        timeout = aiohttp.ClientTimeout(total=300)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(endpoint, json=payload, headers=headers) as resp:
                
                if resp.status == 200:
                    result = await resp.json()
                    
                    if result.get("status") == "success":
                        photo_url = result.get("result", {}).get("photo_url", "")
                        
                        if photo_url:
                            if photo_url.startswith("data:image"):
                                import base64
                                import io
                                base64_data = photo_url.split(",")[1] if "," in photo_url else photo_url
                                image_bytes = base64.b64decode(base64_data)
                                from aiogram.types import BufferedInputFile
                                photo_file = BufferedInputFile(image_bytes, filename="result.png")
                                
                                await message.answer_photo(
                                    photo=photo_file,
                                    caption="Готово! Вот ваше новое изображение."
                                )
                            else:
                                await message.answer_photo(
                                    photo=photo_url,
                                    caption="Готово! Вот ваше новое изображение."
                                )
                            logger.info(f"✅ Photo processed for user {telegram_id}")
                        else:
                            await safe_send_message(
                                message,
                                "Не удалось получить результат. Попробуйте еще раз.",
                                user_id=telegram_id
                            )
                    else:
                        error_message = result.get("message", "Неизвестная ошибка")
                        await safe_send_message(
                            message,
                            f"Возникла проблема: {error_message}",
                            user_id=telegram_id
                        )
                        logger.error(f"❌ Photo processing error for user {telegram_id}: {error_message}")
                
                else:
                    error_body = await resp.text()
                    logger.error(f"❌ GPT Service error {resp.status}: {error_body}")
                    await safe_send_message(
                        message,
                        "Сервис обработки изображений сейчас не отвечает. Пожалуйста, попробуйте позже.",
                        user_id=telegram_id
                    )
                
                await state.clear()
                
                await safe_send_message(
                    message,
                    "Хотите сделать что-то еще?",
                    user_id=telegram_id,
                    parse_mode="HTML",
                    reply_markup=main_menu_keyboard()
                )
    
    except aiohttp.ClientError as e:
        logger.error(f"❌ Network error calling GPT Service: {e}")
        await safe_send_message(
            message,
            "Не могу подключиться к сервису обработки. Попробуйте через некоторое время.",
            user_id=telegram_id
        )
        await state.clear()
    
    except Exception as e:
        logger.error(f"❌ Unexpected error in photo processing: {e}", exc_info=True)
        await safe_send_message(
            message,
            "Произошла непредвиденная ошибка. Мы уже разбираемся.",
            user_id=telegram_id
        )
        await state.clear()


# ============================================================================
# Callback cancel_photo_processing - отмена обработки
# ============================================================================

@router.callback_query(F.data == "cancel_photo_processing")
@handle_telegram_errors
async def callback_cancel_photo_processing(callback: CallbackQuery, state: FSMContext):
    """Отменить процесс обработки фотографии."""
    telegram_id = callback.from_user.id
    
    logger.info(f"🔚 User {telegram_id} cancelled photo processing")
    
    await state.clear()
    
    await callback.message.edit_text(
        "Хорошо, отменил. Вы вернулись в главное меню.",
        reply_markup=main_menu_keyboard()
    )
    
    await callback.answer()
