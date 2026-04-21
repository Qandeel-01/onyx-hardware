"""WebSocket endpoint for real-time shot events and clock synchronization."""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session as DBSession
from uuid import UUID
import json
import logging
from datetime import datetime
import time

from app.database import SessionLocal
from app.models.models import ShotEvent, Session as SessionModel, ClockCalibration
from app.schemas import ShotEventCreate, ShotType

logger = logging.getLogger(__name__)

router = APIRouter()

# Active WebSocket connections per session: session_id → [WebSocket]
active_connections: dict[str, list[WebSocket]] = {}


# ──────────────────────────────────────────────
# DB helper — fresh session per operation,
# never held across await boundaries
# ──────────────────────────────────────────────
def _get_db() -> DBSession:
    return SessionLocal()


@router.websocket("/ws/shots/{session_id}")
async def shot_stream(
    websocket: WebSocket,
    session_id: UUID,
):
    """
    WebSocket endpoint for receiving and broadcasting shot events.

    Handles:
    - Incoming shot events from ESP32 (via BLE → WiFi bridge)
    - SYNC_PING/SYNC_PONG for clock synchronisation
    - Broadcasting to all connected clients on this session

    NOTE: DB session is *not* injected via Depends — holding a single
    SQLAlchemy session open for the entire WebSocket lifetime causes
    pool exhaustion and silent lazy-load failures after commit().
    Instead, a fresh session is acquired and released per DB operation.
    """
    sid_str = str(session_id)

    # Must accept the WebSocket before close(); closing first yields HTTP 403 (uvicorn).
    await websocket.accept()

    # ── Verify session exists ───────────────────────────────────────
    db = _get_db()
    try:
        session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
        if not session:
            await websocket.send_json(
                {"type": "ERROR", "message": "Session not found", "code": 4004}
            )
            await websocket.close(code=4004, reason="Session not found")
            return
    finally:
        db.close()

    # Register connection
    active_connections.setdefault(sid_str, []).append(websocket)
    logger.info(
        f"WebSocket connected: session={session_id}  "
        f"total={len(active_connections[sid_str])}"
    )

    try:
        while True:
            raw_data = await websocket.receive_text()

            try:
                data = json.loads(raw_data)
            except json.JSONDecodeError:
                await websocket.send_json({"type": "ERROR", "message": "Invalid JSON"})
                continue

            message_type = data.get("type")

            # ── SYNC_PING ───────────────────────────────────────────
            if message_type == "SYNC_PING":
                browser_ts = data.get("browser_ts")
                device_ts = int(time.time() * 1000)

                browser_ts_int: int | None = None
                if browser_ts is not None:
                    try:
                        browser_ts_int = int(float(browser_ts))
                    except (TypeError, ValueError):
                        pass

                offset_ms = float(device_ts - browser_ts_int) if browser_ts_int is not None else 0.0

                await websocket.send_json({
                    "type": "SYNC_PONG",
                    "device_ts": device_ts,
                    "echo_browser_ts": browser_ts_int,
                    "offset_ms": offset_ms,
                })
                logger.debug(f"SYNC_PONG sent: session={session_id}")

            # ── SHOT_EVENT ──────────────────────────────────────────
            elif message_type == "SHOT_EVENT":
                try:
                    shot_create = ShotEventCreate(
                        shot_type=data.get("shot_type"),
                        confidence=data.get("confidence"),
                        device_ts=data.get("device_ts_ms", 0),
                        accel_x=data.get("accel_x"),
                        accel_y=data.get("accel_y"),
                        accel_z=data.get("accel_z"),
                        gyro_x=data.get("gyro_x"),
                        gyro_y=data.get("gyro_y"),
                        gyro_z=data.get("gyro_z"),
                    )

                    # Fresh DB session — acquired and released synchronously,
                    # no await between open and close
                    db = _get_db()
                    try:
                        shot_event = ShotEvent(
                            session_id=session_id,
                            shot_type=shot_create.shot_type.value
                                if hasattr(shot_create.shot_type, "value")
                                else shot_create.shot_type,
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
                        # Refresh BEFORE closing the session so attributes
                        # are populated and not expired/lazy-loaded later
                        db.refresh(shot_event)

                        # Capture values while session is still open
                        broadcast_payload = {
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
                        }
                        logger.info(
                            f"Shot saved: {shot_event.shot_type} "
                            f"conf={shot_event.confidence:.2f} "
                            f"session={session_id}"
                        )
                    finally:
                        db.close()

                    await broadcast_to_session(sid_str, broadcast_payload)

                except Exception as e:
                    logger.error(f"Error processing SHOT_EVENT: {e}", exc_info=True)
                    await websocket.send_json({"type": "ERROR", "message": str(e)})

            else:
                logger.warning(f"Unknown message type '{message_type}' on session {session_id}")

    except WebSocketDisconnect:
        _remove_connection(sid_str, websocket)
        logger.info(
            f"WebSocket disconnected: session={session_id}  "
            f"remaining={len(active_connections.get(sid_str, []))}"
        )

    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)
        _remove_connection(sid_str, websocket)


def _remove_connection(session_id: str, ws: WebSocket) -> None:
    conns = active_connections.get(session_id, [])
    if ws in conns:
        conns.remove(ws)
    if not conns and session_id in active_connections:
        del active_connections[session_id]


async def broadcast_to_session(session_id: str, message: dict) -> None:
    """Broadcast a message to all WebSocket clients on a session."""
    if session_id not in active_connections:
        return

    disconnected: list[WebSocket] = []
    for connection in active_connections[session_id]:
        try:
            await connection.send_json(message)
        except Exception as e:
            logger.error(f"Broadcast error: {e}")
            disconnected.append(connection)

    for conn in disconnected:
        _remove_connection(session_id, conn)