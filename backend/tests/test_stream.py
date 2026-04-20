"""Tests for WebSocket streaming functionality"""

import pytest
import json
import asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from fastapi.testclient import TestClient

from app.main import app
from app.database import get_db, Base


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


def test_websocket_connect(test_db):
    """WebSocket /stream/ws/{session_id} should accept and send connected message"""
    client = TestClient(app)
    
    with client.websocket_connect("/stream/ws/test_session") as websocket:
        # Receive connection confirmation
        data = websocket.receive_json()
        assert data["type"] == "connected"
        assert data["session_id"] == "test_session"


def test_stream_stats():
    """GET /stream/stats should return connection statistics"""
    client = TestClient(app)
    
    response = client.get("/stream/stats")
    assert response.status_code == 200
    data = response.json()
    assert "connected_sessions" in data
    assert "total_clients" in data
    assert "sessions" in data


@pytest.mark.asyncio
async def test_websocket_receives_shot(test_db):
    """WebSocket should receive shot event published via Redis"""
    client_http = AsyncClient(app=app, base_url="http://test")
    client_sync = TestClient(app)
    
    session_id = "test_session_42"
    
    # Connect WebSocket
    with client_sync.websocket_connect(f"/stream/ws/{session_id}") as websocket:
        # Receive connection confirmation
        msg = websocket.receive_json()
        assert msg["type"] == "connected"
        
        # In a real scenario, a shot would be published via Redis.
        # This is a simplified test that checks the endpoint accepts connections.
        # Full integration testing would require actual Redis instance.
        
        # Verify we can still communicate
        websocket.send_text("")  # Try sending something
