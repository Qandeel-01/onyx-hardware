"""Main FastAPI application for Project ONYX Live Analysis."""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

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


@app.exception_handler(OperationalError)
async def database_unavailable_handler(request: Request, exc: OperationalError):
    """Turn DB connection failures into a clear 503 instead of a generic 500."""
    logger.error("Database operational error: %s", exc, exc_info=True)
    return JSONResponse(
        status_code=503,
        content={
            "detail": (
                "Database unreachable. Start PostgreSQL (e.g. from repo root: "
                "`docker compose up -d db`). If the API runs on the host, set "
                "backend/.env DATABASE_URL to postgresql://onyx:onyx@localhost:5433/onyx "
                "when using the Compose DB (host port 5433)."
            )
        },
    )


@app.get("/", tags=["health"])
def root():
    """Health check endpoint."""
    return {
        "status": "ok",
        "service": "Project ONYX Live Analysis API",
        "version": "1.0.0",
        "docs_swagger": "/docs",
        "docs_redoc": "/redoc",
        "openapi": "/openapi.json",
        "health": "/health",
        "websocket_shots": "/ws/shots/{session_id}",
    }


@app.get("/health", tags=["health"])
def health_check():
    """Health check; verifies a live DB connection (not just process up)."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except OperationalError as e:
        logger.warning("Health check DB ping failed: %s", e)
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "database": "disconnected",
                "environment": settings.env,
                "hint": (
                    "Start Postgres (`docker compose up -d db`). "
                    "Host API: DATABASE_URL=postgresql://onyx:onyx@localhost:5433/onyx"
                ),
            },
        )
    return {
        "status": "healthy",
        "database": "connected",
        "environment": settings.env,
    }


@app.get("/debug/cors", tags=["debug"])
def debug_cors():
    """Inspect parsed CORS origins (REST preflight); WebSocket does not use this middleware."""
    parsed = [
        x.strip() for x in settings.allowed_origins.split(",") if x.strip()
    ]
    return {"allowed_origins": settings.allowed_origins, "parsed": parsed}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=(settings.env == "development")
    )
