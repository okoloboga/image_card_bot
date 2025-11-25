"""
Photo Processing module - обработка фотографий через нейронную сеть.

Модуль предоставляет:
- REST API для обработки фотографий по промпту
- Интеграцию с сервисом генерации изображений
"""

from .service import process_photo
from .image_client import ImageGenerationClient

__all__ = [
    # Service
    "process_photo",
    # Clients
    "ImageGenerationClient",
]
