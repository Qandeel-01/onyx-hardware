"""Pydantic schemas for request/response validation."""
from pydantic import BaseModel, Field, ConfigDict, field_validator
from datetime import datetime
from uuid import UUID
from typing import Optional
from enum import Enum


class ShotType(str, Enum):
    """Enumeration of shot types."""
    FOREHAND = "Forehand"
    BACKHAND = "Backhand"
    SMASH = "Smash"
    VOLLEY = "Volley"
    BANDEJA = "Bandeja"
    LOB = "Lob"


class ShotEventBase(BaseModel):
    """Base shot event schema."""
    model_config = ConfigDict(from_attributes=True, use_enum_values=False)
    
    shot_type: ShotType
    confidence: float = Field(ge=0.0, le=1.0)
    device_ts: int
    accel_x: Optional[float] = None
    accel_y: Optional[float] = None
    accel_z: Optional[float] = None
    gyro_x: Optional[float] = None
    gyro_y: Optional[float] = None
    gyro_z: Optional[float] = None


class ShotEventCreate(ShotEventBase):
    """Schema for creating a shot event."""
    pass


class ShotEventResponse(ShotEventBase):
    """Schema for shot event response."""
    id: UUID
    session_id: UUID
    wall_clock_ts: Optional[datetime] = None
    frame_index: Optional[int] = None
    court_x: Optional[float] = None
    court_y: Optional[float] = None
    player_bbox: Optional[dict] = None
    pose_keypoints: Optional[list] = None
    created_at: datetime


class SessionCreate(BaseModel):
    """Schema for creating a session."""
    player_id: Optional[UUID] = None
    fps: float = 30.0


class SessionUpdate(BaseModel):
    """Schema for updating a session."""
    ended_at: Optional[datetime] = None
    video_file_path: Optional[str] = None
    sync_quality: Optional[str] = None


class SessionResponse(BaseModel):
    """Schema for session response."""
    id: UUID
    player_id: Optional[UUID] = None
    started_at: datetime
    ended_at: Optional[datetime] = None
    video_file_path: Optional[str] = None
    fps: float
    sync_quality: str
    created_at: datetime
    shot_count: int = 0

    class Config:
        from_attributes = True


class ClockCalibrationBase(BaseModel):
    """Base clock calibration schema."""
    rtt_ms: float
    offset_ms: float
    quality: str


class ClockCalibrationCreate(ClockCalibrationBase):
    """Schema for creating a clock calibration."""
    pass


class ClockCalibrationResponse(ClockCalibrationBase):
    """Schema for clock calibration response."""
    id: UUID
    session_id: UUID
    calibrated_at: datetime

    class Config:
        from_attributes = True


class SyncPingMessage(BaseModel):
    """WebSocket sync ping message."""
    type: str = "SYNC_PING"
    browser_ts: int


class SyncPongMessage(BaseModel):
    """WebSocket sync pong message."""
    type: str = "SYNC_PONG"
    device_ts: int
    echo_browser_ts: int
