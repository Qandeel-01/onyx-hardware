"""FastAPI application entry point for ONYX IoT Backend"""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from app.config import settings
from app.database import init_db, close_db
from app.services.influx_service import influx_service
from app.services.redis_service import redis_service
from app.routers import shots, stream, health

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup and shutdown lifecycle events.
    
    Startup:
      - Initialize database
      - Log service health status
    
    Shutdown:
      - Close connections gracefully
    """
    
    # STARTUP
    logger.info("=" * 60)
    logger.info("ONYX IoT Backend Starting...")
    logger.info("=" * 60)
    
    try:
        await init_db()
        logger.info("✓ Database initialized")
    except Exception as e:
        logger.error(f"✗ Database initialization failed: {e}")
    
    # Log service status
    influxdb_ok = await influx_service.ping()
    logger.info(f"{'✓' if influxdb_ok else '✗'} InfluxDB: {'Ready' if influxdb_ok else 'Unavailable'}")
    
    redis_ok = await redis_service.ping()
    logger.info(f"{'✓' if redis_ok else '✗'} Redis: {'Ready' if redis_ok else 'Unavailable'}")
    
    logger.info("Ready to receive data from ESP32")
    logger.info("=" * 60)
    
    yield  # Server is running
    
    # SHUTDOWN
    logger.info("=" * 60)
    logger.info("ONYX IoT Backend Shutting Down...")
    logger.info("=" * 60)
    
    influx_service.close()
    await redis_service.close()
    await close_db()
    
    logger.info("✓ All connections closed")


# Create FastAPI application
app = FastAPI(
    title="ONYX IoT Backend",
    description="ESP32 → PostgreSQL/InfluxDB/Redis → WebSocket",
    version="1.0.0",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(shots.router)
app.include_router(stream.router)
app.include_router(health.router)


@app.get("/", include_in_schema=False)
async def root():
    """Redirect root to API documentation"""
    return RedirectResponse(url="/docs")


@app.get("/ping")
async def ping():
    """Simple healthcheck endpoint"""
    return {"pong": True}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
