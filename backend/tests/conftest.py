"""Pytest configuration and fixtures for backend tests."""

import sys
from pathlib import Path

# Add parent directory to Python path so 'app' module is discoverable
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.database import Base, get_db

# Test database URL (in-memory SQLite for speed)
SQLALCHEMY_TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="function")
async def test_db():
    """Create an async in-memory SQLite database for each test."""
    engine = create_async_engine(
        SQLALCHEMY_TEST_DATABASE_URL,
        echo=False,
        connect_args={"check_same_thread": False},
    )
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async def override_get_db():
        async with async_session() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    yield async_session

    # Cleanup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
def client(test_db):
    """Create a FastAPI TestClient with overridden database."""
    return TestClient(app)


@pytest.fixture
def anyio_backend():
    """Use asyncio backend for anyio-based tests."""
    return "asyncio"
