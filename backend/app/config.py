"""Configuration management for ONYX backend."""
from pydantic import field_validator
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

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def normalize_allowed_origins(cls, v: object) -> str:
        """Strip wrapping quotes; trim spaces around commas so origins match browsers."""
        if not isinstance(v, str):
            return "http://localhost:3000,http://localhost:5173"
        s = v.strip()
        if len(s) >= 2 and s[0] == s[-1] and s[0] in ('"', "'"):
            s = s[1:-1].strip()
        parts = [p.strip() for p in s.split(",") if p.strip()]
        return ",".join(parts) if parts else "http://localhost:3000,http://localhost:5173"
    
    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached application settings."""
    return Settings()
