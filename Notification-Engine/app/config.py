from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://notify:notify@localhost:5432/notify"
    redis_url: str = "redis://localhost:6379/0"
    rabbitmq_url: str = "amqp://guest:guest@localhost:5672/"

    api_rate_limit_per_minute: int = 1000
    log_level: str = "INFO"

    max_delivery_attempts: int = 5
    base_backoff_seconds: float = 2.0

    failure_simulation_rate: float = 0.0

    queue_name: str = "notifications.priority"
    dlq_name: str = "notifications.dlq"
    exchange_name: str = "notifications"

    broker_connect_on_startup: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()
