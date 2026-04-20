"""Business logic for shot event management"""

import logging
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import ShotEvent
from app.schemas import SensorDataIn

logger = logging.getLogger(__name__)


class ShotService:
    """Service for persisting and querying shot events"""
    
    async def save(
        self,
        db: AsyncSession,
        data: SensorDataIn,
        session_id: str | None = None
    ) -> ShotEvent:
        """
        Create and persist a new ShotEvent.
        
        Args:
            db: Database session
            data: Validated sensor data from ESP32
            session_id: Optional session identifier from request header
        
        Returns:
            Created ShotEvent ORM object
        """
        shot = ShotEvent(
            device_id=data.device_id,
            shot_type=data.shot_type,
            confidence=data.confidence,
            timestamp=data.timestamp,
            ax=data.ax,
            ay=data.ay,
            az=data.az,
            gx=data.gx,
            gy=data.gy,
            gz=data.gz,
            session_id=session_id,
        )
        
        db.add(shot)
        await db.flush()  # Flush to get the ID without committing
        
        logger.debug(f"Shot saved: id={shot.id}, device={data.device_id}, type={data.shot_type}")
        return shot
    
    async def get_shots(
        self,
        db: AsyncSession,
        device_id: str | None = None,
        session_id: str | None = None,
        shot_type: str | None = None,
        min_confidence: float | None = None,
        page: int = 1,
        size: int = 50,
    ) -> tuple[list[ShotEvent], int]:
        """
        Retrieve shots with dynamic filtering and pagination.
        
        Args:
            db: Database session
            device_id: Filter by ESP32 device ID
            session_id: Filter by session ID
            shot_type: Filter by shot classification
            min_confidence: Filter by minimum confidence threshold
            page: Page number (1-indexed)
            size: Results per page
        
        Returns:
            Tuple of (shots list, total count)
        """
        # Build dynamic query
        query = select(ShotEvent)
        
        if device_id:
            query = query.where(ShotEvent.device_id == device_id)
        if session_id:
            query = query.where(ShotEvent.session_id == session_id)
        if shot_type:
            query = query.where(ShotEvent.shot_type == shot_type)
        if min_confidence is not None:
            query = query.where(ShotEvent.confidence >= min_confidence)
        
        # Get total count
        count_query = select(func.count(ShotEvent.id))
        if device_id:
            count_query = count_query.where(ShotEvent.device_id == device_id)
        if session_id:
            count_query = count_query.where(ShotEvent.session_id == session_id)
        if shot_type:
            count_query = count_query.where(ShotEvent.shot_type == shot_type)
        if min_confidence is not None:
            count_query = count_query.where(ShotEvent.confidence >= min_confidence)
        
        total = await db.scalar(count_query)
        total = total or 0  # Ensure total is int, not None
        
        # Apply pagination (1-indexed page)
        offset = (page - 1) * size
        query = query.order_by(ShotEvent.timestamp.desc()).offset(offset).limit(size)
        
        result = await db.execute(query)
        shots = list(result.scalars().all())
        
        return shots, total


# Module-level singleton
shot_service = ShotService()
