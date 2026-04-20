"""Router for shot data ingestion and querying"""

import asyncio
import logging
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.config import settings
from app.schemas import (
    SensorDataIn,
    ShotEventOut,
    ShotListResponse,
    ShotPostResponse,
)
from app.models import ShotEvent
from app.services.shot_service import shot_service
from app.services.influx_service import influx_service
from app.services.redis_service import redis_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/data", tags=["shot-data"])


@router.post("/", response_model=ShotPostResponse, status_code=200)
async def post_shot(
    data: SensorDataIn,
    db: AsyncSession = Depends(get_db),
    x_session_id: str | None = Header(None),
):
    """
    Ingest shot data from ESP32.
    
    1. Validate confidence threshold
    2. Save to PostgreSQL
    3. Write to InfluxDB (fire-and-forget)
    4. Publish via Redis (fire-and-forget)
    
    Headers:
        X-Session-ID: Optional session identifier
    """
    
    # 1. Reject low-confidence shots
    if data.confidence < settings.SHOT_CONFIDENCE_MIN:
        raise HTTPException(
            status_code=422,
            detail=f"confidence {data.confidence} below threshold {settings.SHOT_CONFIDENCE_MIN}",
        )
    
    # 2. Save to PostgreSQL
    shot = await shot_service.save(db, data, x_session_id)
    await db.commit()
    
    logger.info(
        f"Shot recorded: id={shot.id}, device={data.device_id}, "
        f"type={data.shot_type}, conf={data.confidence:.2f}"
    )
    
    # 3. Fire-and-forget: write to InfluxDB
    asyncio.create_task(influx_service.write(data, x_session_id))
    
    # 4. Fire-and-forget: publish via Redis
    channel = f"onyx:shots:{x_session_id}" if x_session_id else "onyx:shots:global"
    payload = {
        "type": "shot",
        "device_id": data.device_id,
        "shot_type": data.shot_type,
        "confidence": data.confidence,
        "timestamp": data.timestamp,
        "session_id": x_session_id,
        "ax": data.ax,
        "ay": data.ay,
        "az": data.az,
        "gx": data.gx,
        "gy": data.gy,
        "gz": data.gz,
    }
    asyncio.create_task(redis_service.publish(channel, payload))
    
    return ShotPostResponse(status="ok", id=shot.id)


@router.get("/shots", response_model=ShotListResponse)
async def get_shots(
    db: AsyncSession = Depends(get_db),
    device_id: str | None = Query(None),
    session_id: str | None = Query(None),
    shot_type: str | None = Query(None),
    min_confidence: float | None = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=500),
):
    """
    Retrieve shots with optional filtering and pagination.
    
    Query Parameters:
        device_id: Filter by device ID
        session_id: Filter by session ID
        shot_type: Filter by shot type (forehand, backhand, smash, etc.)
        min_confidence: Filter by minimum confidence
        page: Page number (1-indexed)
        size: Results per page (1-500)
    """
    
    shots, total = await shot_service.get_shots(
        db,
        device_id=device_id,
        session_id=session_id,
        shot_type=shot_type,
        min_confidence=min_confidence,
        page=page,
        size=size,
    )
    
    return ShotListResponse(
        shots=[ShotEventOut.model_validate(shot) for shot in shots],
        total=total,
        page=page,
        size=size,
    )


@router.get("/shots/{shot_id}", response_model=ShotEventOut)
async def get_shot(
    shot_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Retrieve a specific shot by ID"""
    
    shot = await db.get(ShotEvent, shot_id)
    
    if not shot:
        raise HTTPException(status_code=404, detail="Shot not found")
    
    return ShotEventOut.model_validate(shot)


@router.delete("/shots/{shot_id}", status_code=204)
async def delete_shot(
    shot_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Hard delete a shot event"""
    
    shot = await db.get(ShotEvent, shot_id)
    
    if not shot:
        raise HTTPException(status_code=404, detail="Shot not found")
    
    await db.delete(shot)
    await db.commit()
    
    logger.info(f"Shot deleted: id={shot_id}")
