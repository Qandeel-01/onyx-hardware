"""Async database session management."""

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from fastapi import Depends

from app.config import settings


engine = create_async_engine(
    settings.database_url,
    echo=False,
    future=True,
    pool_size=10,
    max_overflow=20,
)

async_session = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False, future=True
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency to get database session."""
    async with async_session() as session:
        yield session


async def init_db():
    """Initialize database tables."""
    async with engine.begin() as conn:
        # Alembic handles migrations
        pass


async def close_db():
    """Close database connections."""
    await engine.dispose()
