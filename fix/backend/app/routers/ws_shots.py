"""WebSocket endpoint for real-time shot events and clock synchronization."""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.orm import Session as DBSession
from sqlalchemy import select, func
from uuid import UUID
import json
import logging
from datetime import datetime
from app.database import get_db
from app.models.models import ShotEvent, Session as SessionModel, ClockCalibration
from app.schemas import ShotEventCreate, ShotType
import time

logger = logging.getLogger(__name__)

router = APIRouter()

# Active WebSocket connections per session: session_id → [WebSocket]
active_connections: dict[str, list[WebSocket]] = {}


@router.websocket("/ws/shots/{session_id}")
async def shot_stream(
    websocket: WebSocket,
    session_id: UUID,
    db: DBSession = Depends(get_db)
):
    """
    WebSocket endpoint for receiving and broadcasting shot events.
    
    Handles:
    - Incoming shot events from ESP32 (via BLE → WiFi bridge)
    - SYNC_PING/SYNC_PONG for clock synchronization
    - Broadcasting to all connected clients on this session
    """
    await websocket.accept()
    sid_str = str(session_id)
    
    # Verify session exists
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        await websocket.close(code=4004, reason="Session not found")
        return
    
    # Register connection
    active_connections.setdefault(sid_str, []).append(websocket)
    logger.info(f"WebSocket connected to session {session_id}. Total connections: {len(active_connections[sid_str])}")
    
    try:
        while True:
            raw_data = await websocket.receive_text()
            data = json.loads(raw_data)
            
            message_type = data.get("type")
            
            if message_type == "SYNC_PING":
                # Synchronization ping: measure round-trip time
                browser_ts = data.get("browser_ts")
                device_ts = int(time.time() * 1000)  # Current server time in ms
                browser_ts_int: int | None = None
                if browser_ts is not None:
                    try:
                        browser_ts_int = int(float(browser_ts))
                    except (TypeError, ValueError):
                        browser_ts_int = None
                offset_ms = (
                    float(device_ts - browser_ts_int)
                    if browser_ts_int is not None
                    else 0.0
                )

                pong_response = {
                    "type": "SYNC_PONG",
                    "device_ts": device_ts,
                    "echo_browser_ts": browser_ts_int,
                    "offset_ms": offset_ms,
                }
                await websocket.send_json(pong_response)
                logger.debug(f"SYNC_PONG sent for session {session_id}")
            
            elif message_type == "SHOT_EVENT":
                # Real shot event from ESP32
                try:
                    # Validate and create shot event
                    shot_data = {
                        "shot_type": data.get("shot_type"),
                        "confidence": data.get("confidence"),
                        "device_ts": data.get("device_ts_ms", 0),
                        "accel_x": data.get("accel_x"),
                        "accel_y": data.get("accel_y"),
                        "accel_z": data.get("accel_z"),
                        "gyro_x": data.get("gyro_x"),
                        "gyro_y": data.get("gyro_y"),
                        "gyro_z": data.get("gyro_z"),
                    }
                    
                    shot_create = ShotEventCreate(**shot_data)
                    
                    # Save to database
                    shot_event = ShotEvent(
                        session_id=session_id,
                        shot_type=shot_create.shot_type,
                        confidence=shot_create.confidence,
                        device_ts_ms=shot_create.device_ts,
                        accel_x=shot_create.accel_x,
                        accel_y=shot_create.accel_y,
                        accel_z=shot_create.accel_z,
                        gyro_x=shot_create.gyro_x,
                        gyro_y=shot_create.gyro_y,
                        gyro_z=shot_create.gyro_z,
                    )
                    db.add(shot_event)
                    db.commit()
                    
                    logger.info(f"Shot event saved: {shot_event.shot_type} (conf={shot_create.confidence:.2f})")
                    
                    # Broadcast to all listeners on this session
                    await broadcast_to_session(
                        sid_str,
                        {
                            "type": "SHOT_EVENT",
                            "id": str(shot_event.id),
                            "session_id": sid_str,
                            "shot_type": shot_event.shot_type,
                            "confidence": shot_event.confidence,
                            "device_ts_ms": shot_event.device_ts_ms,
                            "timestamp": shot_event.created_at.isoformat(),
                            "accel_x": shot_event.accel_x,
                            "accel_y": shot_event.accel_y,
                            "accel_z": shot_event.accel_z,
                            "gyro_x": shot_event.gyro_x,
                            "gyro_y": shot_event.gyro_y,
                            "gyro_z": shot_event.gyro_z,
                        },
                    )
                    
                except Exception as e:
                    logger.error(f"Error processing shot event: {e}")
                    await websocket.send_json({"type": "ERROR", "message": str(e)})
            
            else:
                # Unknown message type — log and ignore
                logger.warning(f"Unknown message type: {message_type}")
    
    except WebSocketDisconnect:
        active_connections[sid_str].remove(websocket)
        logger.info(f"WebSocket disconnected from session {session_id}. Remaining connections: {len(active_connections[sid_str])}")
    
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        if sid_str in active_connections and websocket in active_connections[sid_str]:
            active_connections[sid_str].remove(websocket)


async def broadcast_to_session(session_id: str, message: dict):
    """Broadcast a message to all WebSocket clients connected to a session."""
    if session_id not in active_connections:
        return
    
    disconnected = []
    for connection in active_connections[session_id]:
        try:
            await connection.send_json(message)
        except Exception as e:
            logger.error(f"Error broadcasting to connection: {e}")
            disconnected.append(connection)
    
    # Clean up disconnected connections
    for conn in disconnected:
        if conn in active_connections[session_id]:
            active_connections[session_id].remove(conn)
