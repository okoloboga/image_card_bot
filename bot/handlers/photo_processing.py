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
from keyboards.keyboards import main_menu_keyboard, create_photo_processing_keyboard, create_photo_upload_keyboard
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
    
    await state.update_data(photo_file_ids=[], prompt=None)
    
    await state.set_state(PhotoProcessingStates.waiting_for_photo)
    
    welcome_text = (
        "🖼️ <b>Мастерская изображений</b>\n\n"
        "Готов преобразить ваши фото! Отправьте мне от 1 до 3 изображений.\n\n"
        "<b>Этап 1:</b> Жду ваше первое изображение."
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
    """Обработка до 3 фото от пользователя."""
    telegram_id = message.from_user.id
    photo = message.photo[-1]
    
    data = await state.get_data()
    photo_file_ids = data.get("photo_file_ids", [])
    
    if len(photo_file_ids) >= 3:
        await safe_send_message(
            message,
            "Вы уже добавили 3 фото. Нажмите 'Готово', чтобы продолжить.",
            user_id=telegram_id,
            reply_markup=create_photo_upload_keyboard()
        )
        return

    photo_file_ids.append(photo.file_id)
    await state.update_data(photo_file_ids=photo_file_ids)
    
    logger.info(f"📸 Photo {len(photo_file_ids)}/3 received from user {telegram_id}, file_id: {photo.file_id}")

    if len(photo_file_ids) == 3:
        await state.set_state(PhotoProcessingStates.waiting_for_prompt)
        await safe_send_message(
            message,
            "✨ <b>3 фото добавлены!</b>\n\n"
            "<b>Этап 2:</b> Теперь расскажите, что бы вы хотели с ними сделать?\n\n"
            "<i>Например: «объедини три фото в одно», «сделай коллаж».</i>",
            user_id=telegram_id,
            parse_mode="HTML",
            reply_markup=create_photo_processing_keyboard()
        )
    else:
        await safe_send_message(
            message,
            f"✅ <b>Фото {len(photo_file_ids)}/3 добавлено.</b>\n\n"
            "Вы можете отправить еще фото или нажать 'Готово', чтобы перейти к следующему шагу.",
            user_id=telegram_id,
            parse_mode="HTML",
            reply_markup=create_photo_upload_keyboard()
        )


@router.message(StateFilter(PhotoProcessingStates.waiting_for_photo))
@handle_telegram_errors
async def process_photo_error(message: Message, state: FSMContext):
    """Обработка некорректного ввода (не фото)."""
    telegram_id = message.from_user.id
    data = await state.get_data()
    photo_file_ids = data.get("photo_file_ids", [])

    if not photo_file_ids:
        await safe_send_message(
            message,
            "Это не похоже на фото. Пожалуйста, отправьте изображение.",
            user_id=telegram_id
        )
    else:
        await safe_send_message(
            message,
            "Пожалуйста, отправьте еще одно изображение или нажмите 'Готово'.",
            user_id=telegram_id,
            reply_markup=create_photo_upload_keyboard()
        )


# ============================================================================
# Callback photos_done - завершение добавления фото
# ============================================================================

@router.callback_query(F.data == "photos_done", StateFilter(PhotoProcessingStates.waiting_for_photo))
@handle_telegram_errors
async def callback_photos_done(callback: CallbackQuery, state: FSMContext):
    """Завершить добавление фото и перейти к вводу промпта."""
    telegram_id = callback.from_user.id
    data = await state.get_data()
    
    if not data.get("photo_file_ids"):
        await callback.answer("Вы не добавили ни одного фото!", show_alert=True)
        return

    logger.info(f"👍 User {telegram_id} finished adding photos.")
    
    await state.set_state(PhotoProcessingStates.waiting_for_prompt)
    
    await callback.message.edit_text(
        "✨ <b>Отличные фото!</b>\n\n"
        "<b>Этап 2:</b> Теперь расскажите, что бы вы хотели с ними сделать?\n\n"
        "<i>Например: «убери фон», «сделай в стиле аниме», «добавь солнечных лучей».</i>",
        parse_mode="HTML",
        reply_markup=create_photo_processing_keyboard()
    )
    await callback.answer()



from sqlalchemy.ext.asyncio import AsyncSession
from database.models import User
from database.crud import use_credits

# Стоимость операций
PHOTO_GENERATION_COST = 40

# ============================================================================
# Обработка промпта
# ============================================================================

@router.message(StateFilter(PhotoProcessingStates.waiting_for_prompt), F.text)
@handle_telegram_errors
async def process_prompt(message: Message, state: FSMContext, session: AsyncSession, db_user: User):
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
    
    await process_photo_with_api(message, state, session, db_user)


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

async def process_photo_with_api(message: Message, state: FSMContext, session: AsyncSession, db_user: User):
    """Отправка данных в GPT сервис для обработки фото."""
    telegram_id = message.from_user.id
    
    # 1. Проверка кредитов
    if db_user.credits_remaining < PHOTO_GENERATION_COST:
        logger.info(f"🚫 User {telegram_id} has not enough credits for photo generation.")
        await safe_send_message(
            message,
            f"У вас недостаточно кредитов для генерации фото (нужно {PHOTO_GENERATION_COST}, у вас {db_user.credits_remaining}).\n"
            "Чтобы пополнить баланс, воспользуйтесь командой /buy_credits.",
            user_id=telegram_id
        )
        await state.clear()
        return

    data = await state.get_data()
    
    photo_file_ids = data.get("photo_file_ids")
    prompt = data.get("prompt")
    
    if not photo_file_ids or not prompt:
        await safe_send_message(
            message,
            "Что-то пошло не так, не хватает данных. Давайте начнем сначала.",
            user_id=telegram_id
        )
        await state.clear()
        return
    
    processing_message = await safe_send_message(
        message,
        f"🔮 <b>Колдую над вашим изображением...</b>\n\n"
        f"Это будет стоить {PHOTO_GENERATION_COST} кредитов. Ваш баланс: {db_user.credits_remaining - PHOTO_GENERATION_COST}\n"
        "Обычно это занимает не больше минуты.",
        user_id=telegram_id,
        parse_mode="HTML"
    )
    
    endpoint = f"{GPT_SERVICE_URL.rstrip('/')}/v1/photo/process"
    payload = {
        "telegram_id": telegram_id,
        "photo_file_ids": photo_file_ids,
        "prompt": prompt
    }
    headers = {
        "Content-Type": "application/json",
        "X-API-KEY": config.api_secret_key
    }
    
    try:
        # Списываем кредит ПЕРЕД запросом
        await use_credits(session, telegram_id, PHOTO_GENERATION_COST)
        logger.info(f"💳 {PHOTO_GENERATION_COST} credits used by user {telegram_id}. Remaining: {db_user.credits_remaining}")

        timeout = aiohttp.ClientTimeout(total=300)
        async with aiohttp.ClientSession(timeout=timeout) as aio_session:
            async with aio_session.post(endpoint, json=payload, headers=headers) as resp:
                
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
    finally:
        # Удаляем сообщение о процессе
        if processing_message:
            await processing_message.delete()


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
