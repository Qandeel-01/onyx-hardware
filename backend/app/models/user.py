"""
User ORM model for Project ONYX.

Represents users in the system with authentication and profile information.
Users can own multiple wearable devices and sessions.
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .device import WearableDevice
    from .session import Session


class User(Base):
    """
    User model representing an athlete or user in the system.
    
    Attributes:
        id: Primary key, auto-incremented.
        email: Unique user email address.
        hashed_password: Bcrypt-hashed password.
        name: User's display name.
        is_active: Whether the user account is active.
        created_at: Timestamp of account creation.
        devices: Relationship to associated WearableDevice records.
        sessions: Relationship to associated Session records.
    """
    
    __tablename__ = "users"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    
    # Relationships
    devices: Mapped[list["WearableDevice"]] = relationship(
        "WearableDevice",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin"
    )
    sessions: Mapped[list["Session"]] = relationship(
        "Session",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin"
    )
    
    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email}, name={self.name})>"
