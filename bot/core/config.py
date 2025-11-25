import os
from typing import Optional
from dataclasses import dataclass
from dotenv import load_dotenv

# Загружаем переменные окружения только если .env файл существует
# В Docker переменные окружения уже установлены через docker-compose.yml
env_file = os.path.join(os.path.dirname(__file__), '..', '..', '.env')
if os.path.exists(env_file):
    load_dotenv(env_file)
else:
    # Пробуем загрузить из текущей директории (для локального запуска)
    load_dotenv(override=False)  # override=False означает, что не перезаписываем существующие переменные


@dataclass
class BotConfig:
    """Конфигурация бота"""
    
    # Telegram Bot
    bot_token: str
    
    # API
    api_secret_key: str = ""
    
    # Настройки
    log_level: str = "INFO"
    debug: bool = False
    
    # Retry настройки
    request_timeout: int = 300
    
    # Адрес GPT сервиса
    gpt_service_url: str = "http://127.0.0.1:9000"
    
    def __post_init__(self):
        """Валидация конфигурации после инициализации"""
        if not self.bot_token:
            raise ValueError("BOT_TOKEN не найден в переменных окружения")


def load_config() -> BotConfig:
    """Загрузить конфигурацию из переменных окружения"""
    bot_token = os.getenv("BOT_TOKEN", "").strip()
    return BotConfig(
        bot_token=bot_token,
        api_secret_key=os.getenv("API_SECRET_KEY", ""),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        debug=os.getenv("DEBUG", "false").lower() == "true",
        request_timeout=int(os.getenv("REQUEST_TIMEOUT", "300")),
        gpt_service_url=os.getenv("GPT_SERVICE_URL", "http://127.0.0.1:9000"),
    )


# Глобальная конфигурация
config = load_config()