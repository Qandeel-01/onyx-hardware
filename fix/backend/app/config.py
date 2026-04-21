"""Configuration management for ONYX backend."""
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Database
    database_url: str = "postgresql://onyx:onyx@localhost:5432/onyx"
    
    # Environment
    env: str = "development"
    log_level: str = "INFO"
    
    # CORS — comma-separated URLs in .env (ALLOWED_ORIGINS)
    allowed_origins: str = "http://localhost:3000,http://localhost:5173"
    
    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached application settings."""
    return Settings()
