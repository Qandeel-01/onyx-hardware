"""
WearableDevice ORM model for Project ONYX.

Represents wearable sensor devices (e.g., IMU wristbands) associated with users.
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .session import Session
    from .user import User


class WearableDevice(Base):
    """
    WearableDevice model representing a wearable sensor device.
    
    Attributes:
        id: Primary key, auto-incremented.
        user_id: Foreign key to User who owns the device.
        mac_address: Unique MAC address of the device.
        firmware_version: Current firmware version on the device.
        last_seen: Last timestamp the device communicated with the server.
        user: Relationship to owning User.
        sessions: Relationship to associated Session records.
    """
    
    __tablename__ = "wearable_devices"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    mac_address: Mapped[str] = mapped_column(String(17), unique=True, index=True)
    firmware_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    last_seen: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="devices", lazy="selectin")
    sessions: Mapped[list["Session"]] = relationship(
        "Session",
        back_populates="device",
        cascade="all, delete-orphan",
        lazy="selectin"
    )
    
    def __repr__(self) -> str:
        return f"<WearableDevice(id={self.id}, mac_address={self.mac_address}, user_id={self.user_id})>"
