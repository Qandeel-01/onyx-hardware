"""WebSocket router for real-time shot event streaming"""

import asyncio
import json
import logging
from typing import Dict, Set
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
import redis.asyncio as redis

from app.config import settings
from app.services.redis_service import redis_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/stream", tags=["streaming"])

# Track connected WebSocket clients per session
connected_clients: Dict[str, Set[WebSocket]] = {}


@router.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """
    WebSocket endpoint for real-time shot events.
    
    Flow:
    1. Accept connection
    2. Subscribe to Redis channels (session-specific + global)
    3. Forward messages to client
    4. Send keepalive pings
    5. Clean up on disconnect
    """
    
    # Enforce max clients
    total_clients = sum(len(clients) for clients in connected_clients.values())
    if total_clients >= settings.MAX_WS_CLIENTS:
        await websocket.close(code=1013, reason="Server at capacity")
        return
    
    # Accept connection
    await websocket.accept()
    
    # Track this client
    if session_id not in connected_clients:
        connected_clients[session_id] = set()
    connected_clients[session_id].add(websocket)
    
    logger.info(
        f"WebSocket connected: session={session_id}, "
        f"total_clients={total_clients + 1}"
    )
    
    # Send connection confirmation
    await websocket.send_json({
        "type": "connected",
        "session_id": session_id,
    })
    
    # Create Redis subscriber for this client
    redis_client = await redis.from_url(
        settings.REDIS_URL,
        decode_responses=True,
    )
    pubsub = redis_client.pubsub()
    
    # Subscribe to both session-specific and global channels
    await pubsub.subscribe(
        f"onyx:shots:{session_id}",
        "onyx:shots:global",
    )
    
    async def redis_listener():
        """Listen for messages on Redis channels"""
        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    try:
                        # Parse and forward the shot event
                        payload = json.loads(message["data"])
                        await websocket.send_json(payload)
                    except json.JSONDecodeError:
                        logger.error(f"Invalid JSON from Redis: {message['data']}")
                    except Exception as e:
                        logger.error(f"Error forwarding message: {e}")
                        break
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Redis listener error: {e}")
        finally:
            await pubsub.unsubscribe()
            await redis_client.close()
    
    async def keepalive_sender():
        """Send keepalive pings every 20 seconds"""
        try:
            while True:
                await asyncio.sleep(20)
                await websocket.send_json({"type": "ping"})
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Keepalive error: {e}")
    
    # Run both tasks concurrently
    try:
        await asyncio.gather(
            redis_listener(),
            keepalive_sender(),
        )
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: session={session_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        # Clean up
        connected_clients[session_id].discard(websocket)
        if not connected_clients[session_id]:
            del connected_clients[session_id]
        
        await redis_client.close()
        logger.info(f"WebSocket cleanup complete: session={session_id}")


@router.get("/stats")
async def get_stream_stats():
    """
    Get current WebSocket connection statistics.
    
    Returns:
        connected_sessions: Number of sessions with active connections
        total_clients: Total number of connected clients
        sessions: Breakdown by session
    """
    
    stats = {
        "connected_sessions": len(connected_clients),
        "total_clients": sum(len(clients) for clients in connected_clients.values()),
        "sessions": {
            session_id: len(clients)
            for session_id, clients in connected_clients.items()
        },
    }
    
    return stats
