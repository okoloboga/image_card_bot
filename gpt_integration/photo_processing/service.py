"""
Сервис обработки фотографий через нейронную сеть.

Основные функции:
- Обработка фотографий по промпту пользователя
- Интеграция с API генерации изображений
"""

import os
import logging
import httpx
from typing import Optional, Dict, Any
from datetime import datetime

from .image_client import ImageGenerationClient

logger = logging.getLogger(__name__)


async def _get_telegram_file_url(bot_token: str, file_id: str) -> str:
    """Get public URL for a Telegram file."""
    async with httpx.AsyncClient() as client:
        get_file_url = f"https://api.telegram.org/bot{bot_token}/getFile"
        try:
            response = await client.post(get_file_url, json={"file_id": file_id}, timeout=20.0)
            response.raise_for_status()
            data = response.json()
            if not data.get("ok"):
                raise ValueError(f"Telegram API error: {data.get('description')}")
            file_path = data["result"]["file_path"]
            return f"https://api.telegram.org/file/bot{bot_token}/{file_path}"
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error getting file path from Telegram: {e.response.text}")
            raise ValueError("Failed to get file path from Telegram.") from e
        except Exception as e:
            logger.error(f"Error getting file path from Telegram: {e}")
            raise ValueError("Failed to get file path from Telegram.") from e


async def process_photo(
    telegram_id: int,
    photo_file_id: str,
    prompt: str,
    user_id: Optional[int] = None,
    bot_token: Optional[str] = None
) -> Dict[str, Any]:
    """
    Обработать фотографию по промпту пользователя.
    
    Args:
        telegram_id: ID пользователя в Telegram
        photo_file_id: Telegram file_id исходного фото
        prompt: Текстовое описание желаемого результата
        user_id: ID пользователя в основной БД (опционально)
        bot_token: Токен Telegram бота (для загрузки фото)
    
    Returns:
        Dict с результатом обработки:
        - photo_url: URL обработанного изображения
        - processing_time: Время обработки в секундах
    
    Raises:
        ValueError: При некорректных входных данных
        Exception: При ошибках обработки
    """
    start_time = datetime.now()
    
    logger.info(f"📸 Processing photo for user {telegram_id} with prompt: {prompt[:50]}...")
    
    client = None
    try:
        # 1. Получаем токен бота
        if not bot_token:
            bot_token = os.getenv("BOT_TOKEN")
            if not bot_token:
                raise ValueError("BOT_TOKEN not set")
        
        # 2. Получаем URL фото из Telegram
        logger.info(f"📥 Getting file URL from Telegram for: {photo_file_id}")
        image_url = await _get_telegram_file_url(bot_token, photo_file_id)
        
        # 3. Создаем клиент для API генерации изображений
        api_key = os.getenv("IMAGE_GEN_API_KEY") or os.getenv("COMET_API_KEY")
        if not api_key:
            raise ValueError("IMAGE_GEN_API_KEY or COMET_API_KEY not set")
            
        base_url = os.getenv("IMAGE_GEN_BASE_URL") or "https://api.cometapi.com"
        model = os.getenv("IMAGE_GEN_MODEL") or "gemini-2.5-flash-image"
        timeout_str = os.getenv("IMAGE_GEN_TIMEOUT", "120.0")
        timeout = float(timeout_str)

        client = ImageGenerationClient(api_key=api_key, base_url=base_url, model=model, timeout=timeout)
        
        # 4. Обрабатываем изображение
        logger.info(f"🎨 Processing image with prompt: {prompt[:50]}...")
        photo_data_uri = await client.process_image(image_url, prompt)
        
        photo_url = photo_data_uri 
        
        processing_time = (datetime.now() - start_time).total_seconds()

        logger.info(f"✅ Photo processed successfully in {processing_time:.2f}s")
        
        return {
            "photo_url": photo_url,
            "processing_time": processing_time,
        }
    
    except ValueError as e:
        logger.error(f"❌ Validation error: {e}")
        raise
    
    except Exception as e:
        total_time = (datetime.now() - start_time).total_seconds()
        logger.error(f"❌ Photo processing failed after {total_time:.2f}s: {e}")
        raise
    finally:
        if client:
            await client.close()
