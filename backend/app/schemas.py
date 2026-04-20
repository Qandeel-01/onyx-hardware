"""Pydantic request/response models for FastAPI"""

from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import List, Optional
from datetime import datetime


class SensorDataIn(BaseModel):
    """
    Validates the exact ESP32 payload format.
    All fields are required.
    """
    
    device_id: str = Field(..., min_length=1, max_length=64)
    timestamp: float = Field(..., gt=0, description="Unix seconds from ESP32")
    shot_type: str = Field(
        ...,
        pattern="^(forehand|backhand|smash|volley|lob|serve|unknown)$",
        description="Shot classification"
    )
    confidence: float = Field(..., ge=0.0, le=1.0)
    ax: float
    ay: float
    az: float
    gx: float
    gy: float
    gz: float
    
    @field_validator("timestamp")
    @classmethod
    def validate_timestamp(cls, v):
        """Ensure timestamp is positive"""
        if v <= 0:
            raise ValueError("timestamp must be > 0")
        return v


class ShotEventOut(BaseModel):
    """Response model for ShotEvent ORM objects"""
    
    id: int
    device_id: str
    shot_type: str
    confidence: float
    timestamp: float
    received_at: datetime
    ax: float
    ay: float
    az: float
    gx: float
    gy: float
    gz: float
    session_id: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)


class ShotListResponse(BaseModel):
    """Paginated list of shot events"""
    
    shots: List[ShotEventOut]
    total: int
    page: int
    size: int


class HealthResponse(BaseModel):
    """Health check status for all backends"""
    
    status: str
    postgres: bool
    influxdb: bool
    redis: bool


class ShotPostResponse(BaseModel):
    """Response after successfully posting a shot"""
    
    status: str
    id: int
