"""
Base declarative class for all SQLAlchemy ORM models.

This module provides the declarative base that all models inherit from,
following SQLAlchemy 2.0 patterns.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """
    Base class for all ORM models in Project ONYX.
    
    All database model classes should inherit from this class to ensure
    consistent configuration and behavior across the application.
    """
    pass
