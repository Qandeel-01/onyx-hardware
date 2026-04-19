"""
Clock synchronization and WebSocket router for Project ONYX.
Handles SNTP sync, flash calibration, and real-time WebSocket communication.
"""

from fastapi import APIRouter, WebSocket, Depends, HTTPException, status, WebSocketException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import json
import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional
from pydantic import BaseModel

from app.database import get_session
from app.models.session import Session, SessionClockSync
from app.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["clock"])

# Request/Response Models
class FlashCalibrationRequest(BaseModel):
    """Request model for flash calibration."""
    residual_offset_ms: float
    quality: str


class FlashCalibrationResponse(BaseModel):
    """Response model for flash calibration."""
    calibration_state: str
    flash_residual_offset_ms: float
    timestamp_utc_ms: float


class SNTPMessage(BaseModel):
    """SNTP synchronization message."""
    type: str
    client_id: str
    t1_ms: Optional[float] = None  # Client's send time
    t2_ms: Optional[float] = None  # Server's receive time
    t3_ms: Optional[float] = None  # Server's send time
    t4_ms: Optional[float] = None  # Client's receive time


class ShotMessage(BaseModel):
    """Shot event message."""
    type: str
    shot_id: int
    shot_type: str
    court_x_m: float
    court_y_m: float
    confidence: float
    timestamp_utc_ms: float


# WebSocket registry to track active connections per session
# Format: {session_id: {client_id: websocket}}
sessions_ws: Dict[int, Dict[str, WebSocket]] = {}


@router.post("/sessions/{session_id}/calibrate/flash", response_model=FlashCalibrationResponse)
async def calibrate_flash(
    session_id: int,
    request: FlashCalibrationRequest,
    db: AsyncSession = Depends(get_session),
    current_user: Dict = Depends(get_current_user)
) -> FlashCalibrationResponse:
    """
    Calibrate session using flash detection residual offset.
    
    Updates session with the flash calibration data and marks calibration as completed.
    
    Args:
        session_id: ID of the session to calibrate
        request: Flash calibration data (offset and quality)
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Updated calibration state and offset
        
    Raises:
        HTTPException: 404 if session not found
    """
    stmt = select(Session).where(Session.id == session_id)
    session = (await db.execute(stmt)).scalar_one_or_none()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    
    try:
        session.flash_residual_offset_ms = request.residual_offset_ms
        session.calibration_state = "completed"
        session.calibration_timestamp_utc_ms = datetime.utcnow().timestamp() * 1000
        
        # Optionally store calibration quality for analysis
        if not hasattr(session, 'calibration_quality'):
            session.calibration_quality = request.quality
        
        await db.commit()
        await db.refresh(session)
        
        logger.info(
            f"Flash calibration completed for session {session_id}: "
            f"offset={request.residual_offset_ms}ms, quality={request.quality}"
        )
        
        return FlashCalibrationResponse(
            calibration_state=session.calibration_state,
            flash_residual_offset_ms=session.flash_residual_offset_ms,
            timestamp_utc_ms=session.calibration_timestamp_utc_ms
        )
    
    except Exception as e:
        logger.error(f"Error during flash calibration for session {session_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to calibrate session"
        )


@router.websocket("/sessions/{session_id}/ws/{client_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    session_id: int,
    client_id: str,
    db: AsyncSession = Depends(get_session)
):
    """
    WebSocket endpoint for real-time synchronization and shot events.
    
    Accepts SNTP synchronization messages, shot events, and broadcasts to all
    connected clients for a given session.
    
    Args:
        websocket: WebSocket connection
        session_id: ID of the session
        client_id: Unique identifier for this client
        db: Database session
    """
    # Verify session exists
    stmt = select(Session).where(Session.id == session_id)
    session = (await db.execute(stmt)).scalar_one_or_none()
    
    if not session:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Session not found")
        return
    
    await websocket.accept()
    
    # Initialize session registry if needed
    if session_id not in sessions_ws:
        sessions_ws[session_id] = {}
    
    sessions_ws[session_id][client_id] = websocket
    logger.info(f"Client {client_id} connected to session {session_id} WebSocket")
    
    try:
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=300.0)
                message = json.loads(data)
                
                message_type = message.get("type")
                
                if message_type == "sntp":
                    # Handle SNTP synchronization
                    current_time_ms = datetime.utcnow().timestamp() * 1000
                    response = {
                        "type": "sntp_response",
                        "client_id": client_id,
                        "t1_ms": message.get("t1_ms"),
                        "t2_ms": current_time_ms,
                        "t3_ms": current_time_ms,
                        "t4_ms": None
                    }
                    
                    # Send response back to requesting client
                    try:
                        await websocket.send_json(response)
                    except Exception as e:
                        logger.warning(f"Failed to send SNTP response to {client_id}: {str(e)}")
                
                elif message_type == "shot":
                    # Handle shot event - broadcast to all connected clients
                    shot_data = message.get("data", {})
                    broadcast_message = {
                        "type": "shot",
                        "client_id": client_id,
                        "data": shot_data,
                        "broadcast_timestamp_utc_ms": datetime.utcnow().timestamp() * 1000
                    }
                    
                    # Broadcast to all clients in session
                    disconnected_clients = []
                    for client_ws_id, client_ws in sessions_ws[session_id].items():
                        try:
                            await client_ws.send_json(broadcast_message)
                        except Exception as e:
                            logger.warning(f"Failed to broadcast to {client_ws_id}: {str(e)}")
                            disconnected_clients.append(client_ws_id)
                    
                    # Clean up disconnected clients
                    for disconnected_id in disconnected_clients:
                        if disconnected_id in sessions_ws[session_id]:
                            del sessions_ws[session_id][disconnected_id]
                
                elif message_type == "ping":
                    # Heartbeat/health check
                    await websocket.send_json({
                        "type": "pong",
                        "timestamp_utc_ms": datetime.utcnow().timestamp() * 1000
                    })
                
                elif message_type == "calibration_complete":
                    # Notify all clients that calibration is complete
                    calibration_message = {
                        "type": "calibration_complete",
                        "client_id": client_id,
                        "timestamp_utc_ms": datetime.utcnow().timestamp() * 1000
                    }
                    
                    for client_ws in sessions_ws[session_id].values():
                        try:
                            await client_ws.send_json(calibration_message)
                        except Exception as e:
                            logger.warning(f"Failed to broadcast calibration complete: {str(e)}")
                
                else:
                    logger.warning(f"Unknown message type received: {message_type}")
            
            except asyncio.TimeoutError:
                # Send ping to keep connection alive
                try:
                    await websocket.send_json({
                        "type": "ping",
                        "timestamp_utc_ms": datetime.utcnow().timestamp() * 1000
                    })
                except Exception as e:
                    logger.warning(f"Failed to send ping to {client_id}: {str(e)}")
                    break
            
            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON received from {client_id}")
                try:
                    await websocket.send_json({
                        "type": "error",
                        "detail": "Invalid JSON format"
                    })
                except Exception:
                    break
    
    except Exception as e:
        logger.error(f"WebSocket error for client {client_id} in session {session_id}: {str(e)}")
    
    finally:
        # Clean up on disconnect
        if session_id in sessions_ws and client_id in sessions_ws[session_id]:
            del sessions_ws[session_id][client_id]
            logger.info(f"Client {client_id} disconnected from session {session_id}")
        
        # Clean up empty session registry
        if session_id in sessions_ws and len(sessions_ws[session_id]) == 0:
            del sessions_ws[session_id]


@router.get("/sessions/{session_id}/connected-clients")
async def get_connected_clients(
    session_id: int,
    db: AsyncSession = Depends(get_session),
    current_user: Dict = Depends(get_current_user)
) -> Dict[str, any]:
    """
    Get list of currently connected WebSocket clients for a session.
    
    Args:
        session_id: ID of the session
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Dictionary with session info and connected client count
    """
    stmt = select(Session).where(Session.id == session_id)
    session = (await db.execute(stmt)).scalar_one_or_none()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    
    connected_count = len(sessions_ws.get(session_id, {}))
    client_ids = list(sessions_ws.get(session_id, {}).keys())
    
    return {
        "session_id": session_id,
        "connected_count": connected_count,
        "client_ids": client_ids,
        "timestamp_utc_ms": datetime.utcnow().timestamp() * 1000
    }


@router.post("/sessions/{session_id}/broadcast-message")
async def broadcast_message(
    session_id: int,
    message: Dict,
    db: AsyncSession = Depends(get_session),
    current_user: Dict = Depends(get_current_user)
) -> Dict[str, int]:
    """
    Broadcast a message to all connected WebSocket clients in a session.
    
    Args:
        session_id: ID of the session
        message: Message to broadcast
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Number of clients the message was sent to
        
    Raises:
        HTTPException: 404 if session not found
    """
    stmt = select(Session).where(Session.id == session_id)
    session = (await db.execute(stmt)).scalar_one_or_none()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    
    if session_id not in sessions_ws:
        return {"sent_to": 0}
    
    sent_count = 0
    failed_clients = []
    
    broadcast_payload = {
        **message,
        "server_timestamp_utc_ms": datetime.utcnow().timestamp() * 1000
    }
    
    for client_id, ws in sessions_ws[session_id].items():
        try:
            await ws.send_json(broadcast_payload)
            sent_count += 1
        except Exception as e:
            logger.warning(f"Failed to send broadcast to {client_id}: {str(e)}")
            failed_clients.append(client_id)
    
    # Clean up failed clients
    for client_id in failed_clients:
        if client_id in sessions_ws[session_id]:
            del sessions_ws[session_id][client_id]
    
    logger.info(f"Broadcast sent to {sent_count} clients in session {session_id}")
    
    return {
        "sent_to": sent_count,
        "failed": len(failed_clients)
    }
