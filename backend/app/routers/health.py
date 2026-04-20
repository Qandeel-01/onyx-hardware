"""Health check router for all backend services"""

import asyncio
import logging
from fastapi import APIRouter, HTTPException
from sqlalchemy import text

from app.database import get_db, engine
from app.schemas import HealthResponse
from app.services.influx_service import influx_service
from app.services.redis_service import redis_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/", response_model=HealthResponse)
async def health_check():
    """
    Health check for all three backends (PostgreSQL, InfluxDB, Redis).
    Pings all services in parallel.
    """
    
    # Ping all services in parallel
    postgres_ok, influxdb_ok, redis_ok = await asyncio.gather(
        _check_postgres(),
        influx_service.ping(),
        redis_service.ping(),
        return_exceptions=True,
    )
    
    # Convert exceptions to False
    postgres_ok = postgres_ok if isinstance(postgres_ok, bool) else False
    influxdb_ok = influxdb_ok if isinstance(influxdb_ok, bool) else False
    redis_ok = redis_ok if isinstance(redis_ok, bool) else False
    
    status = "ok" if all([postgres_ok, influxdb_ok, redis_ok]) else "degraded"
    
    return HealthResponse(
        status=status,
        postgres=postgres_ok,
        influxdb=influxdb_ok,
        redis=redis_ok,
    )


@router.get("/ready")
async def readiness_check():
    """
    Readiness probe for load balancers.
    Returns 200 only if PostgreSQL is reachable.
    """
    
    try:
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        return {"status": "ready"}
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        raise HTTPException(status_code=503, detail="Database not ready")


async def _check_postgres() -> bool:
    """Check PostgreSQL connectivity"""
    try:
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.warning(f"PostgreSQL check failed: {e}")
        return False
