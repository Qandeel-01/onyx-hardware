"""Configuration management for Project ONYX backend."""

from typing import List

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings from environment variables."""

    # Database
    database_url: str = "postgresql+asyncpg://onyx:onyx_dev@db:5432/onyx"

    # JWT
    secret_key: str = "dev-secret-change-in-prod"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440

    # CORS
    cors_origins: List[str] = ["http://localhost:5173", "http://localhost:3000"]

    # Clock sync
    max_sync_samples_per_batch: int = 10
    sync_interval_seconds: int = 30

    # Flash detection
    flash_detection_prominence: float = 15.0
    flash_detection_min_distance_frames: int = 5
    flash_expected_count: int = 3

    # CV worker
    cv_frame_skip: int = 3
    yolo_model_path: str = "/app/models/yolov8n-pose.pt"

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
