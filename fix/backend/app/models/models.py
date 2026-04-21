"""SQLAlchemy ORM models for ONYX."""
from sqlalchemy import Column, String, Float, Integer, DateTime, Text, Boolean, ForeignKey, BigInteger
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship, Mapped, mapped_column
from datetime import datetime
from typing import Optional, List
from uuid import UUID as PyUUID
import uuid
from app.database import Base


class Session(Base):
    """Represents a padel analysis session."""
    
    __tablename__ = "sessions"

    id: Mapped[PyUUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    player_id: Mapped[Optional[PyUUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    video_file_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    fps: Mapped[float] = mapped_column(Float, default=30.0)
    sync_quality: Mapped[str] = mapped_column(String(50), default="none")  # 'none' | 'estimated' | 'calibrated'
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    # Relationships
    shot_events: Mapped[List["ShotEvent"]] = relationship("ShotEvent", back_populates="session", cascade="all, delete-orphan")
    clock_calibrations: Mapped[List["ClockCalibration"]] = relationship("ClockCalibration", back_populates="session", cascade="all, delete-orphan")
    video_segments: Mapped[List["VideoSegment"]] = relationship("VideoSegment", back_populates="session", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Session {self.id}>"


class ShotEvent(Base):
    """Represents a single shot event captured by wearable."""
    
    __tablename__ = "shot_events"

    id: Mapped[PyUUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[PyUUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False)
    shot_type: Mapped[str] = mapped_column(String(50), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    device_ts_ms: Mapped[int] = mapped_column(BigInteger, nullable=False)
    wall_clock_ts: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    frame_index: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    accel_x: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    accel_y: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    accel_z: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    gyro_x: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    gyro_y: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    gyro_z: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    court_x: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    court_y: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    player_bbox: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    pose_keypoints: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    # Relationships
    session: Mapped["Session"] = relationship("Session", back_populates="shot_events")

    def __repr__(self):
        return f"<ShotEvent {self.id} {self.shot_type} @ {self.device_ts_ms}ms>"


class ClockCalibration(Base):
    """Represents a clock sync calibration event."""
    
    __tablename__ = "clock_calibrations"

    id: Mapped[PyUUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[PyUUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False)
    calibrated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    rtt_ms: Mapped[float] = mapped_column(Float, nullable=False)
    offset_ms: Mapped[float] = mapped_column(Float, nullable=False)
    quality: Mapped[str] = mapped_column(String(50), nullable=False)

    # Relationships
    session: Mapped["Session"] = relationship("Session", back_populates="clock_calibrations")

    def __repr__(self):
        return f"<ClockCalibration {self.id} RTT={self.rtt_ms}ms>"


class VideoSegment(Base):
    """Represents a recorded video segment for a session."""
    
    __tablename__ = "video_segments"

    id: Mapped[PyUUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[PyUUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    start_frame: Mapped[int] = mapped_column(Integer, default=0)
    end_frame: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    capture_started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    processed: Mapped[bool] = mapped_column(Boolean, default=False)

    # Relationships
    session: Mapped["Session"] = relationship("Session", back_populates="video_segments")

    def __repr__(self):
        return f"<VideoSegment {self.id} {self.file_path}>"
