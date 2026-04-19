"""
Session ORM models for Project ONYX.

Models for recording sessions, clock synchronization, and video storage.
Includes Session, SessionClockSync, and SessionVideo models.
"""

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

from sqlalchemy import Enum as SQLEnum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .device import WearableDevice
    from .events import SensorEvent
    from .user import User


class SessionStatus(str, Enum):
    """Enum for session recording status."""
    CREATED = "created"
    RECORDING = "recording"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class CalibrationState(str, Enum):
    """Enum for session calibration progress."""
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class Session(Base):
    """
    Session model representing a recording session.
    
    Captures calibration data, timing metadata, and references to associated
    sensor events and video recordings.
    
    Attributes:
        id: Primary key, auto-incremented.
        user_id: Foreign key to owning User.
        device_id: Foreign key to associated WearableDevice.
        status: Current recording status.
        calibration_state: Calibration progress state.
        court_corners: JSON array of court corner coordinates for perspective calibration.
        flash_residual_offset_ms: Calibrated offset between flash detection and video frame.
        session_start_utc_ms: UTC timestamp when session started.
        session_end_utc_ms: UTC timestamp when session ended.
        created_at: Server-side creation timestamp.
        user: Relationship to owning User.
        device: Relationship to associated WearableDevice.
        clock_syncs: Relationship to clock synchronization records.
        videos: Relationship to video recordings.
        sensor_events: Relationship to sensor events.
    """
    
    __tablename__ = "sessions"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("wearable_devices.id"), index=True)
    status: Mapped[SessionStatus] = mapped_column(
        SQLEnum(SessionStatus),
        default=SessionStatus.CREATED
    )
    calibration_state: Mapped[CalibrationState] = mapped_column(
        SQLEnum(CalibrationState),
        default=CalibrationState.NOT_STARTED
    )
    court_corners: Mapped[dict[str, Any] | None] = mapped_column(nullable=True)
    flash_residual_offset_ms: Mapped[float | None] = mapped_column(nullable=True)
    session_start_utc_ms: Mapped[float | None] = mapped_column(nullable=True, index=True)
    session_end_utc_ms: Mapped[float | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, index=True)
    
    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="sessions", lazy="selectin")
    device: Mapped["WearableDevice"] = relationship("WearableDevice", back_populates="sessions", lazy="selectin")
    clock_syncs: Mapped[list["SessionClockSync"]] = relationship(
        "SessionClockSync",
        back_populates="session",
        cascade="all, delete-orphan",
        lazy="selectin"
    )
    videos: Mapped[list["SessionVideo"]] = relationship(
        "SessionVideo",
        back_populates="session",
        cascade="all, delete-orphan",
        lazy="selectin"
    )
    sensor_events: Mapped[list["SensorEvent"]] = relationship(
        "SensorEvent",
        back_populates="session",
        cascade="all, delete-orphan",
        lazy="select"
    )
    
    def __repr__(self) -> str:
        return (
            f"<Session(id={self.id}, user_id={self.user_id}, "
            f"device_id={self.device_id}, status={self.status})>"
        )


class SessionClockSync(Base):
    """
    SessionClockSync model for clock synchronization data.
    
    Stores the four-way handshake timestamps for NTP-style clock synchronization
    between device and server to establish temporal correspondence.
    
    Attributes:
        id: Primary key, auto-incremented.
        session_id: Foreign key to associated Session.
        t1_device_ms: Timestamp on device when sync request sent (milliseconds).
        t2_server_utc_ms: Timestamp on server when request received (UTC milliseconds).
        t3_server_utc_ms: Timestamp on server when response sent (UTC milliseconds).
        t4_device_ms: Timestamp on device when response received (milliseconds).
        created_at: Server-side creation timestamp.
        session: Relationship to associated Session.
    """
    
    __tablename__ = "session_clock_syncs"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id"), index=True)
    t1_device_ms: Mapped[float] = mapped_column()
    t2_server_utc_ms: Mapped[float] = mapped_column()
    t3_server_utc_ms: Mapped[float] = mapped_column()
    t4_device_ms: Mapped[float] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, index=True)
    
    session: Mapped["Session"] = relationship("Session", back_populates="clock_syncs", lazy="selectin")
    
    def __repr__(self) -> str:
        return f"<SessionClockSync(id={self.id}, session_id={self.session_id})>"


class SessionVideo(Base):
    """
    SessionVideo model representing a video file for a session.
    
    Stores metadata about encoded video recordings captured during a session.
    
    Attributes:
        id: Primary key, auto-incremented.
        session_id: Foreign key to associated Session.
        file_path: Path to the encoded video file.
        fps: Frames per second of the video.
        frame_count: Total number of frames in the video.
        duration_seconds: Total duration of the video in seconds.
        codec: Codec used for encoding (e.g., 'h264', 'vp9').
        encoding_status: Status of video encoding pipeline.
        created_at: Server-side creation timestamp.
        session: Relationship to associated Session.
    """
    
    __tablename__ = "session_videos"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id"), index=True)
    file_path: Mapped[str] = mapped_column(String(512), unique=True)
    fps: Mapped[float | None] = mapped_column(nullable=True)
    frame_count: Mapped[int | None] = mapped_column(nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(nullable=True)
    codec: Mapped[str | None] = mapped_column(String(50), nullable=True)
    encoding_status: Mapped[str] = mapped_column(String(50), default="pending")
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, index=True)
    
    session: Mapped["Session"] = relationship("Session", back_populates="videos", lazy="selectin")
    
    def __repr__(self) -> str:
        return (
            f"<SessionVideo(id={self.id}, session_id={self.session_id}, "
            f"file_path={self.file_path})>"
        )
