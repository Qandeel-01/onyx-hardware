"""
Event ORM models for Project ONYX.

Models for sensor events, video frame events, and fused shot detections.
Includes SensorEvent, VideoFrameEvent, and FusedShot models.
"""

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .session import Session, SessionVideo
    from .events import SensorEvent, VideoFrameEvent


class SensorEvent(Base):
    """
    SensorEvent model for inertial measurement unit (IMU) sensor data.
    
    Captures accelerometer, gyroscope, and orientation data from wearable device,
    along with shot type classification from the device's local model.
    """
    
    __tablename__ = "sensor_events"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id"), index=True)
    device_ts_ms: Mapped[float] = mapped_column(index=True)
    shot_type: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    confidence: Mapped[float | None] = mapped_column(nullable=True)
    accel_x: Mapped[float | None] = mapped_column(nullable=True)
    accel_y: Mapped[float | None] = mapped_column(nullable=True)
    accel_z: Mapped[float | None] = mapped_column(nullable=True)
    gyro_x: Mapped[float | None] = mapped_column(nullable=True)
    gyro_y: Mapped[float | None] = mapped_column(nullable=True)
    gyro_z: Mapped[float | None] = mapped_column(nullable=True)
    euler_roll: Mapped[float | None] = mapped_column(nullable=True)
    euler_pitch: Mapped[float | None] = mapped_column(nullable=True)
    euler_yaw: Mapped[float | None] = mapped_column(nullable=True)
    raw_data: Mapped[dict[str, Any] | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, index=True)
    
    session: Mapped["Session"] = relationship("Session", back_populates="sensor_events", lazy="selectin")
    
    def __repr__(self) -> str:
        return f"<SensorEvent(id={self.id}, session_id={self.session_id}, shot_type={self.shot_type})>"


class VideoFrameEvent(Base):
    """
    VideoFrameEvent model for vision-based detection from video frames.
    
    Captures pose estimation, ball court coordinates, and person detection
    from video analysis.
    """
    
    __tablename__ = "video_frame_events"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id"), index=True)
    video_id: Mapped[int | None] = mapped_column(ForeignKey("session_videos.id"), nullable=True, index=True)
    frame_index: Mapped[int | None] = mapped_column(nullable=True)
    frame_utc_ms: Mapped[float | None] = mapped_column(nullable=True, index=True)
    court_x_m: Mapped[float | None] = mapped_column(nullable=True)
    court_y_m: Mapped[float | None] = mapped_column(nullable=True)
    pose_keypoints: Mapped[list[dict[str, Any]] | None] = mapped_column(nullable=True)
    pose_quality: Mapped[float | None] = mapped_column(nullable=True)
    person_count: Mapped[int | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, index=True)
    
    session: Mapped["Session"] = relationship("Session", lazy="selectin")
    video: Mapped["SessionVideo | None"] = relationship("SessionVideo", lazy="selectin")
    
    def __repr__(self) -> str:
        return f"<VideoFrameEvent(id={self.id}, session_id={self.session_id}, frame_index={self.frame_index})>"


class FusedShot(Base):
    """
    FusedShot model for sensor and vision fusion results.
    
    Represents a shot detection combining evidence from IMU sensor
    and video vision analysis.
    """
    
    __tablename__ = "fused_shots"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id"), index=True)
    sensor_event_id: Mapped[int | None] = mapped_column(ForeignKey("sensor_events.id"), nullable=True, unique=True, index=True)
    video_frame_event_id: Mapped[int | None] = mapped_column(ForeignKey("video_frame_events.id"), nullable=True, index=True)
    shot_type: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    court_x_m: Mapped[float | None] = mapped_column(nullable=True)
    court_y_m: Mapped[float | None] = mapped_column(nullable=True)
    sensor_confidence: Mapped[float | None] = mapped_column(nullable=True)
    vision_confidence: Mapped[float | None] = mapped_column(nullable=True)
    fusion_confidence: Mapped[float | None] = mapped_column(nullable=True)
    fusion_metadata: Mapped[dict[str, Any] | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, index=True)
    
    session: Mapped["Session"] = relationship("Session", lazy="selectin")
    sensor_event: Mapped["SensorEvent | None"] = relationship("SensorEvent", lazy="selectin")
    video_frame_event: Mapped["VideoFrameEvent | None"] = relationship("VideoFrameEvent", lazy="selectin")
    
    def __repr__(self) -> str:
        return f"<FusedShot(id={self.id}, session_id={self.session_id}, shot_type={self.shot_type})>"
