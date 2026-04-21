"""REST API endpoints for session management."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session as DBSession
from sqlalchemy import select, func, desc
from uuid import UUID
from datetime import datetime
from typing import Optional
import logging
from app.database import get_db
from app.models.models import Session, ShotEvent, ClockCalibration
from app.schemas import SessionResponse, ShotEventResponse, ClockCalibrationResponse, ShotType
from app.schemas import (
    SessionCreate,
    SessionUpdate,
    SessionResponse,
    ShotEventResponse,
    ClockCalibrationResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["sessions"])


@router.post("/sessions", response_model=SessionResponse)
def create_session(
    session_create: SessionCreate,
    db: DBSession = Depends(get_db)
):
    """
    Create a new analysis session.
    
    Returns session ID (UUID) to use for WebSocket connection.
    """
    session = Session(
        player_id=session_create.player_id,
        fps=session_create.fps,
        sync_quality="none"
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    
    logger.info(f"Session created: {session.id}")
    
    return SessionResponse(
        id=session.id,
        player_id=session.player_id,
        started_at=session.started_at,
        ended_at=session.ended_at,
        video_file_path=session.video_file_path,
        fps=session.fps,
        sync_quality=session.sync_quality,
        created_at=session.created_at,
        shot_count=0
    )


@router.get("/sessions/{session_id}", response_model=SessionResponse)
def get_session(
    session_id: UUID,
    db: DBSession = Depends(get_db)
):
    """Retrieve session details."""
    session = db.query(Session).filter(Session.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    shot_count = db.query(func.count(ShotEvent.id)).filter(
        ShotEvent.session_id == session_id
    ).scalar() or 0
    
    return SessionResponse(
        id=session.id,
        player_id=session.player_id,
        started_at=session.started_at,
        ended_at=session.ended_at,
        video_file_path=session.video_file_path,
        fps=session.fps,
        sync_quality=session.sync_quality,
        created_at=session.created_at,
        shot_count=shot_count
    )


@router.patch("/sessions/{session_id}", response_model=SessionResponse)
def update_session(
    session_id: UUID,
    session_update: SessionUpdate,
    db: DBSession = Depends(get_db)
):
    """Update session details."""
    session = db.query(Session).filter(Session.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    if session_update.ended_at is not None:
        session.ended_at = session_update.ended_at
    if session_update.video_file_path is not None:
        session.video_file_path = session_update.video_file_path
    if session_update.sync_quality is not None:
        session.sync_quality = session_update.sync_quality
    
    db.commit()
    db.refresh(session)
    
    shot_count = db.query(func.count(ShotEvent.id)).filter(
        ShotEvent.session_id == session_id
    ).scalar() or 0
    
    logger.info(f"Session updated: {session_id}")
    
    return SessionResponse(
        id=session.id,
        player_id=session.player_id,
        started_at=session.started_at,
        ended_at=session.ended_at,
        video_file_path=session.video_file_path,
        fps=session.fps,
        sync_quality=session.sync_quality,
        created_at=session.created_at,
        shot_count=shot_count
    )


@router.get("/sessions/{session_id}/shots", response_model=list[ShotEventResponse])
def get_session_shots(
    session_id: UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: DBSession = Depends(get_db)
):
    """
    Retrieve all shot events for a session.
    
    Results ordered by device_ts_ms (oldest first).
    Supports pagination via skip/limit.
    """
    session = db.query(Session).filter(Session.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    shots = db.query(ShotEvent).filter(
        ShotEvent.session_id == session_id
    ).order_by(ShotEvent.device_ts_ms).offset(skip).limit(limit).all()
    
    return [
        ShotEventResponse(
            id=shot.id,
            session_id=shot.session_id,
            shot_type=ShotType(shot.shot_type),
            confidence=shot.confidence,
            device_ts=shot.device_ts_ms,
            wall_clock_ts=shot.wall_clock_ts,
            frame_index=shot.frame_index,
            court_x=shot.court_x,
            court_y=shot.court_y,
            player_bbox=shot.player_bbox,
            pose_keypoints=shot.pose_keypoints,
            created_at=shot.created_at
        )
        for shot in shots
    ]


@router.get("/sessions/{session_id}/shots/stats")
def get_session_shot_stats(
    session_id: UUID,
    db: DBSession = Depends(get_db)
):
    """
    Get aggregated shot statistics for a session.
    
    Returns:
    - Total shot count
    - Distribution by shot type
    - Average confidence per type
    """
    session = db.query(Session).filter(Session.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    stats = db.query(
        ShotEvent.shot_type,
        func.count(ShotEvent.id).label("count"),
        func.avg(ShotEvent.confidence).label("avg_confidence"),
        func.max(ShotEvent.confidence).label("max_confidence"),
        func.min(ShotEvent.confidence).label("min_confidence")
    ).filter(
        ShotEvent.session_id == session_id
    ).group_by(ShotEvent.shot_type).all()
    
    total = sum([s[1] for s in stats])  # Extract count (second column)
    
    return {
        "session_id": str(session_id),
        "total_shots": total,
        "distribution": [
            {
                "shot_type": s[0],
                "count": s[1],
                "percentage": (s[1] / total * 100) if total > 0 else 0,
                "avg_confidence": float(s[2]) if s[2] else 0.0,
                "max_confidence": float(s[3]) if s[3] else 0.0,
                "min_confidence": float(s[4]) if s[4] else 0.0,
            }
            for s in stats
        ]
    }


@router.post("/sessions/{session_id}/calibrations", response_model=ClockCalibrationResponse)
def create_clock_calibration(
    session_id: UUID,
    rtt_ms: float,
    offset_ms: float,
    db: DBSession = Depends(get_db)
):
    """
    Record a clock synchronization calibration event.
    
    Called after SYNC_PING/PONG handshake completes.
    """
    session = db.query(Session).filter(Session.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Determine quality tier
    if rtt_ms < 5:
        quality = "good"
    elif rtt_ms < 20:
        quality = "acceptable"
    else:
        quality = "poor"
    
    calibration = ClockCalibration(
        session_id=session_id,
        rtt_ms=rtt_ms,
        offset_ms=offset_ms,
        quality=quality
    )
    
    # Update session sync_quality
    session.sync_quality = "calibrated"
    
    db.add(calibration)
    db.commit()
    db.refresh(calibration)
    
    logger.info(f"Clock calibration recorded: RTT={rtt_ms}ms, offset={offset_ms}ms, quality={quality}")
    
    return ClockCalibrationResponse(
        id=calibration.id,
        session_id=calibration.session_id,
        calibrated_at=calibration.calibrated_at,
        rtt_ms=calibration.rtt_ms,
        offset_ms=calibration.offset_ms,
        quality=calibration.quality
    )


@router.get("/sessions/{session_id}/calibrations", response_model=list[ClockCalibrationResponse])
def get_calibrations(
    session_id: UUID,
    db: DBSession = Depends(get_db)
):
    """Retrieve all clock calibration events for a session."""
    session = db.query(Session).filter(Session.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    calibrations = db.query(ClockCalibration).filter(
        ClockCalibration.session_id == session_id
    ).order_by(ClockCalibration.calibrated_at).all()
    
    return [
        ClockCalibrationResponse(
            id=c.id,
            session_id=c.session_id,
            calibrated_at=c.calibrated_at,
            rtt_ms=c.rtt_ms,
            offset_ms=c.offset_ms,
            quality=c.quality
        )
        for c in calibrations
    ]
