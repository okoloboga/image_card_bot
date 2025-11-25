"""
GPT Integration Service - главный роутер для всех GPT функционалов.

Модули:
- card_generation: генерация карточек товаров через GPT
- photo_processing: обработка фотографий
"""

import os
import asyncio
import logging
import time
from typing import Any, Dict, List, Optional
from pathlib import Path
from dotenv import load_dotenv

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp
from starlette.middleware import Middleware

# Загружаем переменные окружения из корневого .env файла
# В Docker переменные окружения уже установлены через docker-compose.yml
env_file = Path(__file__).parent.parent / ".env"
if env_file.exists():
    load_dotenv(env_file)
else:
    # Пробуем загрузить из текущей директории (для обратной совместимости)
    load_dotenv(override=False)

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

# Import modules
from gpt_integration.card_generation.service import generate_card as card_generation_service
from gpt_integration.photo_processing.service import process_photo

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Отключаем стандартный логгер uvicorn.access
uvicorn_access_logger = logging.getLogger("uvicorn.access")
uvicorn_access_logger.handlers = []
uvicorn_access_logger.propagate = False

class CustomAccessLogMiddleware(BaseHTTPMiddleware):
    """
    Кастомный middleware для логирования запросов, исключая /health.
    """
    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.access_logger = logging.getLogger("gpt_integration.access")
        self.access_logger.setLevel(logging.INFO)
        if not self.access_logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self.access_logger.addHandler(handler)

    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        
        response = await call_next(request)
        
        process_time = time.time() - start_time
        formatted_process_time = f"{process_time:.4f}s"

        if request.url.path != "/health":
            self.access_logger.info(
                f'{request.client.host}:{request.client.port} - "{request.method} {request.url.path} HTTP/{request.scope["http_version"]}" '
                f'{response.status_code} {formatted_process_time}'
            )
        
        return response

app = FastAPI(
    title="GPT Integration Service", 
    version="1.0.0",
    middleware=[Middleware(CustomAccessLogMiddleware)]
)


# ============================================================================
# Pydantic Models
# ============================================================================

class CardGenerationRequest(BaseModel):
    telegram_id: int
    photo_file_id: str
    characteristics: Dict[str, str]
    target_audience: str
    selling_points: str
    semantic_core_text: Optional[str] = None


class PhotoProcessingRequest(BaseModel):
    telegram_id: int
    photo_file_ids: List[str]
    prompt: str
    user_id: Optional[int] = None


# ============================================================================
# Health Check
# ============================================================================

@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


# ============================================================================
# Card Generation Endpoints
# ============================================================================

@app.post("/v1/card/generate")
async def card_generate(
    req: CardGenerationRequest,
    x_api_key: Optional[str] = Header(None)
) -> Dict[str, Any]:
    """
    Генерация карточки товара через GPT.
    """
    expected_key = os.getenv("API_SECRET_KEY", "")
    if not x_api_key or x_api_key != expected_key:
        raise HTTPException(status_code=403, detail="Invalid or missing API key")
    
    logger.info(f"🎨 Generating card for telegram_id={req.telegram_id}")
    
    try:
        result = card_generation_service(
            characteristics=req.characteristics,
            target_audience=req.target_audience,
            selling_points=req.selling_points,
            semantic_core_text=req.semantic_core_text
        )
        
        if "ERROR" in result.get("card", ""):
             return {
                "status": "error",
                "card": result.get("card", "")
            }

        return {
            "status": "success",
            "card": result.get("card", "")
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Unexpected error in card generation endpoint: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


# ============================================================================
# Photo Processing Endpoints
# ============================================================================

@app.post("/v1/photo/process")
async def photo_process(
    req: PhotoProcessingRequest,
    x_api_key: Optional[str] = Header(None)
) -> Dict[str, Any]:
    """
    Обработка фотографии по промпту пользователя.
    """
    expected_key = os.getenv("API_SECRET_KEY", "")
    if not x_api_key or x_api_key != expected_key:
        raise HTTPException(status_code=403, detail="Invalid or missing API key")
    
    logger.info(f"📸 Processing photo for telegram_id={req.telegram_id}")
    
    try:
        result = await process_photo(
            telegram_id=req.telegram_id,
            photo_file_ids=req.photo_file_ids,
            prompt=req.prompt,
            user_id=req.user_id
        )
        
        return {
            "status": "success",
            "result": result
        }
    
    except ValueError as e:
        logger.error(f"❌ Validation error: {e}")
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )
    
    except Exception as e:
        logger.error(f"❌ Photo processing error: {e}", exc_info=True)
        
        # Определяем тип ошибки для понятного сообщения
        error_message = str(e)
        
        if "timeout" in error_message.lower():
            return {
                "status": "error",
                "error_type": "timeout",
                "message": "Превышено время ожидания обработки"
            }
        elif "api" in error_message.lower() or "network" in error_message.lower():
            return {
                "status": "error",
                "error_type": "api_error",
                "message": "Ошибка при обращении к сервису обработки изображений"
            }
        else:
            return {
                "status": "error",
                "error_type": "processing__error",
                "message": f"Ошибка обработки: {error_message}"
            }

# ============================================================================
# Main Entry Point
# ============================================================================

if __name__ == "__main__":
    logger.info("Starting GPT service")
    port_str = os.getenv("GPT_PORT") or "9001"
    try:
        port = int(port_str)
    except ValueError:
        logger.error(f"Invalid port '{port_str}', using default 9001.")
        port = 9001
    
    import uvicorn
    uvicorn.run("gpt_integration.service:app", host="0.0.0.0", port=port)
