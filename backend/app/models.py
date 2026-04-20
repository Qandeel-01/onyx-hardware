"""SQLAlchemy ORM models for IoT shot events"""

from datetime import datetime
from sqlalchemy import Float, String, DateTime, Index, func
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class ShotEvent(Base):
    """
    Shot event recorded from ESP32 wearable device.
    Stores accelerometer, gyroscope, and ML inference data.
    """
    
    __tablename__ = "shot_events"
    
    # Primary key
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    
    # Device identification
    device_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    
    # Shot classification
    shot_type: Mapped[str] = mapped_column(String(32), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    
    # Timing (Unix seconds from ESP32)
    timestamp: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    received_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    
    # Accelerometer (m/s²)
    ax: Mapped[float] = mapped_column(Float, nullable=False)
    ay: Mapped[float] = mapped_column(Float, nullable=False)
    az: Mapped[float] = mapped_column(Float, nullable=False)
    
    # Gyroscope (rad/s)
    gx: Mapped[float] = mapped_column(Float, nullable=False)
    gy: Mapped[float] = mapped_column(Float, nullable=False)
    gz: Mapped[float] = mapped_column(Float, nullable=False)
    
    # Session tracking
    session_id: Mapped[str] = mapped_column(String(64), nullable=True, index=True)
    
    # Composite index for efficient querying
    __table_args__ = (
        Index("idx_device_timestamp", "device_id", "timestamp"),
    )
