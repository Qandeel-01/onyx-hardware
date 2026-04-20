"""Tests for shot data ingestion and querying"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.main import app
from app.database import get_db, Base
from app.config import settings
from app.models import ShotEvent


# Test database setup
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def test_db():
    """Create an in-memory test database"""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async_session_local = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async def override_get_db():
        async with async_session_local() as session:
            yield session
    
    app.dependency_overrides[get_db] = override_get_db
    
    yield
    
    await engine.dispose()


@pytest.fixture
async def client(test_db):
    """FastAPI test client"""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_post_shot_success(client):
    """POST /data with valid payload should return 200"""
    payload = {
        "device_id": "esp32_01",
        "timestamp": 1713456789.0,
        "shot_type": "cover_drive",
        "confidence": 0.92,
        "ax": 0.12, "ay": -0.34, "az": 9.81,
        "gx": 1.2, "gy": 0.5, "gz": -0.8,
    }
    
    response = await client.post("/data/", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert "id" in response.json()


@pytest.mark.asyncio
async def test_post_shot_low_confidence(client):
    """POST /data with low confidence should return 422"""
    payload = {
        "device_id": "esp32_01",
        "timestamp": 1713456789.0,
        "shot_type": "smash",
        "confidence": 0.1,  # Below minimum
        "ax": 0.12, "ay": -0.34, "az": 9.81,
        "gx": 1.2, "gy": 0.5, "gz": -0.8,
    }
    
    response = await client.post("/data/", json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_post_shot_missing_field(client):
    """POST /data with missing field should return 422"""
    payload = {
        "device_id": "esp32_01",
        "timestamp": 1713456789.0,
        "shot_type": "volley",
        "confidence": 0.85,
        # Missing 'az'
        "ax": 0.12, "ay": -0.34,
        "gx": 1.2, "gy": 0.5, "gz": -0.8,
    }
    
    response = await client.post("/data/", json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_get_shots_empty(client):
    """GET /data/shots with no data should return empty list"""
    response = await client.get("/data/shots")
    assert response.status_code == 200
    data = response.json()
    assert data["shots"] == []
    assert data["total"] == 0
    assert data["page"] == 1


@pytest.mark.asyncio
async def test_get_shots_filtered(client):
    """GET /data/shots should filter by shot_type"""
    # Insert 3 smash shots and 2 volley shots
    for i in range(3):
        payload = {
            "device_id": "esp32_01",
            "timestamp": 1713456789.0 + i,
            "shot_type": "smash",
            "confidence": 0.85,
            "ax": 0.12, "ay": -0.34, "az": 9.81,
            "gx": 1.2, "gy": 0.5, "gz": -0.8,
        }
        await client.post("/data/", json=payload)
    
    for i in range(2):
        payload = {
            "device_id": "esp32_01",
            "timestamp": 1713456800.0 + i,
            "shot_type": "volley",
            "confidence": 0.90,
            "ax": 0.12, "ay": -0.34, "az": 9.81,
            "gx": 1.2, "gy": 0.5, "gz": -0.8,
        }
        await client.post("/data/", json=payload)
    
    # Filter by shot_type=smash
    response = await client.get("/data/shots?shot_type=smash")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 3
    assert all(shot["shot_type"] == "smash" for shot in data["shots"])


@pytest.mark.asyncio
async def test_get_shot_not_found(client):
    """GET /data/shots/{id} for non-existent shot should return 404"""
    response = await client.get("/data/shots/99999")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_shot(client):
    """DELETE /data/shots/{id} should remove shot"""
    # Insert a shot
    payload = {
        "device_id": "esp32_01",
        "timestamp": 1713456789.0,
        "shot_type": "serve",
        "confidence": 0.88,
        "ax": 0.12, "ay": -0.34, "az": 9.81,
        "gx": 1.2, "gy": 0.5, "gz": -0.8,
    }
    post_response = await client.post("/data/", json=payload)
    shot_id = post_response.json()["id"]
    
    # Delete it
    delete_response = await client.delete(f"/data/shots/{shot_id}")
    assert delete_response.status_code == 204
    
    # Verify it's gone
    get_response = await client.get(f"/data/shots/{shot_id}")
    assert get_response.status_code == 404
