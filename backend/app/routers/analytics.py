"""Analytics queries for fused shots and session insights."""

import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database import get_session
from app.models.events import FusedShot

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/sessions/{session_id}/overview")
async def get_session_overview(session_id: int, db: AsyncSession = Depends(get_session)):
    """Get overview stats for a session.
    
    Returns:
        - total_shots: Total number of shots detected
        - avg_confidence: Average fusion confidence
        - shot_types: Distribution by shot type
    """
    stmt = select(FusedShot).where(FusedShot.session_id == session_id)
    shots = (await db.execute(stmt)).scalars().all()
    
    if not shots:
        return {
            "session_id": session_id,
            "total_shots": 0,
            "avg_confidence": 0.0,
            "shot_types": {},
        }
    
    # Calculate stats
    total_shots = len(shots)
    avg_confidence = sum(s.fusion_confidence or 0 for s in shots) / total_shots
    
    # Group by shot type
    shot_types = {}
    for shot in shots:
        shot_type = shot.shot_type or "unknown"
        shot_types[shot_type] = shot_types.get(shot_type, 0) + 1
    
    return {
        "session_id": session_id,
        "total_shots": total_shots,
        "avg_confidence": avg_confidence,
        "shot_types": shot_types,
    }


@router.get("/sessions/{session_id}/shots/timeline")
async def get_shots_timeline(session_id: int, db: AsyncSession = Depends(get_session)):
    """Get shots ordered by time.
    
    Returns:
        List of shots with timestamps and metadata
    """
    stmt = select(FusedShot).where(FusedShot.session_id == session_id).order_by(FusedShot.created_at)
    shots = (await db.execute(stmt)).scalars().all()
    
    return [
        {
            "id": s.id,
            "shot_type": s.shot_type,
            "court_x_m": s.court_x_m,
            "court_y_m": s.court_y_m,
            "fusion_confidence": s.fusion_confidence,
            "created_at": s.created_at.isoformat() if s.created_at else None,
        }
        for s in shots
    ]


@router.get("/sessions/{session_id}/shots/distribution")
async def get_shots_distribution(session_id: int, db: AsyncSession = Depends(get_session)):
    """Get spatial distribution of shots on court.
    
    Returns:
        List of court coordinates with shot counts
    """
    stmt = select(FusedShot).where(FusedShot.session_id == session_id)
    shots = (await db.execute(stmt)).scalars().all()
    
    # Bin shots into 1m × 1m grid squares
    bins = {}
    for shot in shots:
        if shot.court_x_m is not None and shot.court_y_m is not None:
            bin_key = (int(shot.court_x_m), int(shot.court_y_m))
            bins[bin_key] = bins.get(bin_key, 0) + 1
    
    return [
        {
            "court_x_bin": x,
            "court_y_bin": y,
            "shot_count": count,
        }
        for (x, y), count in sorted(bins.items())
    ]
