"""
Session management router for Project ONYX.
Handles CRUD operations for padel sessions, video recording, and shot data retrieval.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_session
from app.models.session import Session, SessionClockSync
from app.models.events import SensorEvent, FusedShot
from app.auth import get_current_user
from datetime import datetime
import json
from typing import Optional, List, Dict, Any
from pydantic import BaseModel

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


# Request/Response Models
class SessionCreateRequest(BaseModel):
    """Request model for creating a new session."""
    user_id: int
    device_id: int


class SessionUpdateRequest(BaseModel):
    """Request model for updating session status."""
    status: Optional[str] = None
    calibration_state: Optional[str] = None


class VideoFinalizeRequest(BaseModel):
    """Request model for finalizing video upload."""
    file_path: str


class SessionResponse(BaseModel):
    """Response model for session data."""
    id: int
    user_id: int
    device_id: int
    status: str
    calibration_state: str
    session_start_utc_ms: float
    session_end_utc_ms: Optional[float] = None


class FusedShotResponse(BaseModel):
    """Response model for fused shot data."""
    id: int
    shot_type: str
    court_x_m: float
    court_y_m: float
    fusion_confidence: float
    timestamp_utc_ms: float


@router.post("/", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
async def create_session(
    request: SessionCreateRequest,
    db: AsyncSession = Depends(get_session),
    current_user: Dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Create a new padel session.
    
    Args:
        request: Session creation request containing user_id and device_id
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Created session data with ID and initial status
    """
    session = Session(
        user_id=request.user_id,
        device_id=request.device_id,
        status="created",
        calibration_state="not_started",
        session_start_utc_ms=datetime.utcnow().timestamp() * 1000
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    
    return {
        "id": session.id,
        "user_id": session.user_id,
        "device_id": session.device_id,
        "status": session.status,
        "calibration_state": session.calibration_state,
        "session_start_utc_ms": session.session_start_utc_ms
    }


@router.get("/{session_id}", response_model=Dict[str, Any])
async def get_session(
    session_id: int,
    db: AsyncSession = Depends(get_session),
    current_user: Dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Retrieve session details by ID.
    
    Args:
        session_id: ID of the session to retrieve
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Session data including status and calibration state
        
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
    
    return {
        "id": session.id,
        "user_id": session.user_id,
        "device_id": session.device_id,
        "status": session.status,
        "calibration_state": session.calibration_state,
        "session_start_utc_ms": session.session_start_utc_ms,
        "session_end_utc_ms": session.session_end_utc_ms,
        "flash_residual_offset_ms": session.flash_residual_offset_ms
    }


@router.get("/user/{user_id}", response_model=List[Dict[str, Any]])
async def get_user_sessions(
    user_id: int,
    db: AsyncSession = Depends(get_session),
    current_user: Dict = Depends(get_current_user)
) -> List[Dict[str, Any]]:
    """
    Retrieve all sessions for a specific user.
    
    Args:
        user_id: ID of the user
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        List of sessions for the user
    """
    stmt = select(Session).where(Session.user_id == user_id)
    sessions = (await db.execute(stmt)).scalars().all()
    
    return [
        {
            "id": s.id,
            "user_id": s.user_id,
            "device_id": s.device_id,
            "status": s.status,
            "calibration_state": s.calibration_state,
            "session_start_utc_ms": s.session_start_utc_ms,
            "session_end_utc_ms": s.session_end_utc_ms
        }
        for s in sessions
    ]


@router.patch("/{session_id}", response_model=Dict[str, Any])
async def patch_session(
    session_id: int,
    updates: SessionUpdateRequest,
    db: AsyncSession = Depends(get_session),
    current_user: Dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Partially update session properties.
    
    Args:
        session_id: ID of the session to update
        updates: Fields to update (status, calibration_state)
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Updated session ID
        
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
    
    update_data = updates.dict(exclude_unset=True)
    for key, value in update_data.items():
        if hasattr(session, key):
            setattr(session, key, value)
    
    await db.commit()
    await db.refresh(session)
    
    return {
        "id": session.id,
        "status": session.status,
        "calibration_state": session.calibration_state
    }


@router.post("/{session_id}/video/start", response_model=Dict[str, Any])
async def start_video(
    session_id: int,
    db: AsyncSession = Depends(get_session),
    current_user: Dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Start video recording for a session.
    
    Args:
        session_id: ID of the session
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Updated session status
        
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
    
    session.status = "recording"
    await db.commit()
    await db.refresh(session)
    
    return {
        "status": session.status,
        "session_id": session_id,
        "timestamp": datetime.utcnow().timestamp() * 1000
    }


@router.post("/{session_id}/video/finalize", response_model=Dict[str, Any])
async def finalize_video(
    session_id: int,
    request: VideoFinalizeRequest,
    db: AsyncSession = Depends(get_session),
    current_user: Dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Finalize video recording and store file path.
    
    Args:
        session_id: ID of the session
        request: Video finalization request with file_path
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Video ID and file path confirmation
        
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
    
    # Import SessionVideo model (assumes it exists in app.models.session)
    from app.models.session import SessionVideo
    
    video = SessionVideo(
        session_id=session_id,
        file_path=request.file_path,
        created_at_utc_ms=datetime.utcnow().timestamp() * 1000
    )
    db.add(video)
    await db.commit()
    await db.refresh(video)
    
    return {
        "video_id": video.id,
        "file_path": video.file_path,
        "session_id": session_id
    }


@router.get("/{session_id}/fused-shots", response_model=List[Dict[str, Any]])
async def get_fused_shots(
    session_id: int,
    db: AsyncSession = Depends(get_session),
    current_user: Dict = Depends(get_current_user)
) -> List[Dict[str, Any]]:
    """
    Retrieve all fused shots for a session.
    
    Args:
        session_id: ID of the session
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        List of fused shots with position and confidence data
    """
    stmt = select(FusedShot).where(FusedShot.session_id == session_id)
    shots = (await db.execute(stmt)).scalars().all()
    
    return [
        {
            "id": s.id,
            "shot_type": s.shot_type,
            "court_x_m": s.court_x_m,
            "court_y_m": s.court_y_m,
            "fusion_confidence": s.fusion_confidence,
            "timestamp_utc_ms": s.timestamp_utc_ms
        }
        for s in shots
    ]


@router.post("/{session_id}/end", response_model=Dict[str, Any])
async def end_session(
    session_id: int,
    db: AsyncSession = Depends(get_session),
    current_user: Dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    End a session and mark it as completed.
    
    Args:
        session_id: ID of the session to end
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Session ID and completion status
        
    Raises:
        HTTPException: 404 if session not found
        HTTPException: 400 if session not properly calibrated
    """
    stmt = select(Session).where(Session.id == session_id)
    session = (await db.execute(stmt)).scalar_one_or_none()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    
    if session.calibration_state != "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Session must be calibrated before ending"
        )
    
    session.status = "completed"
    session.session_end_utc_ms = datetime.utcnow().timestamp() * 1000
    await db.commit()
    await db.refresh(session)
    
    return {
        "id": session.id,
        "status": session.status,
        "session_end_utc_ms": session.session_end_utc_ms
    }


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    session_id: int,
    db: AsyncSession = Depends(get_session),
    current_user: Dict = Depends(get_current_user)
):
    """
    Delete a session and associated data.
    
    Args:
        session_id: ID of the session to delete
        db: Database session
        current_user: Current authenticated user
        
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
    
    await db.delete(session)
    await db.commit()
