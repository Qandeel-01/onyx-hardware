"""Configuration management for Project ONYX IoT backend."""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Global configuration from environment variables and .env file"""
    
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://onyx:onyx@localhost:5432/onyx"
    
    # InfluxDB
    INFLUXDB_URL: str = "http://localhost:8086"
    INFLUXDB_TOKEN: str = ""
    INFLUXDB_ORG: str = "onyx"
    INFLUXDB_BUCKET: str = "sensor_data"
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379"
    
    # Business logic
    SHOT_CONFIDENCE_MIN: float = 0.5
    MAX_WS_CLIENTS: int = 50
    
    # CORS
    CORS_ORIGINS: list = ["*"]
    
    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache
def get_settings() -> Settings:
    """Singleton settings instance"""
    return Settings()


settings = get_settings()
