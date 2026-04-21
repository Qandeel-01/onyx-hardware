"""Main FastAPI application for Project ONYX Live Analysis."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
from app.config import get_settings
from app.database import engine, Base
from app.models.models import Session, ShotEvent, ClockCalibration, VideoSegment
from app.routers import sessions, ws_shots

# Create database tables
Base.metadata.create_all(bind=engine)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

settings = get_settings()

# Create FastAPI app
app = FastAPI(
    title="Project ONYX Live Analysis API",
    description="Real-time padel shot analysis with wearable IoT integration",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        x.strip() for x in settings.allowed_origins.split(",") if x.strip()
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(sessions.router)
app.include_router(ws_shots.router)


@app.get("/", tags=["health"])
def root():
    """Health check endpoint."""
    return {
        "status": "ok",
        "service": "Project ONYX Live Analysis API",
        "version": "1.0.0"
    }


@app.get("/health", tags=["health"])
def health_check():
    """Detailed health check."""
    return {
        "status": "healthy",
        "database": "connected",
        "environment": settings.env
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=(settings.env == "development")
    )
