# 📘 FastAPI Backend — Developer Quick Reference

## Key Files Overview

| File | Purpose |
|------|---------|
| `app/main.py` | FastAPI application entry point, router mounting |
| `app/database.py` | SQLAlchemy engine, SessionLocal, Base class |
| `app/config.py` | Settings from environment variables |
| `app/schemas.py` | Pydantic models for API validation |
| `app/models/models.py` | SQLAlchemy ORM models (Session, ShotEvent, ClockCalibration, VideoSegment) |
| `app/routers/sessions.py` | REST endpoints (/api/sessions/*) |
| `app/routers/ws_shots.py` | WebSocket endpoint (/ws/shots/{session_id}) |
| `alembic/versions/001_initial.py` | Initial database migration |

---

## Database Models at a Glance

### Session
```python
Session(
    id: UUID,
    player_id: UUID | None,
    started_at: datetime,
    ended_at: datetime | None,
    video_file_path: str | None,
    fps: float = 30.0,
    sync_quality: str = "none",  # 'none' | 'estimated' | 'calibrated'
    shot_events: list[ShotEvent],
    clock_calibrations: list[ClockCalibration],
    video_segments: list[VideoSegment]
)
```

### ShotEvent
```python
ShotEvent(
    id: UUID,
    session_id: UUID,
    shot_type: str,  # 'Forehand' | 'Backhand' | 'Smash' | 'Volley' | 'Bandeja' | 'Lob'
    confidence: float,  # 0.0–1.0
    device_ts_ms: int,  # Raw ESP32 millis()
    wall_clock_ts: datetime | None,  # Corrected by clock offset
    frame_index: int | None,  # Computed from wall_clock_ts
    accel_x, accel_y, accel_z: float | None,
    gyro_x, gyro_y, gyro_z: float | None,
    court_x, court_y: float | None,  # Post-YOLO processing
    player_bbox: dict | None,  # {x,y,w,h}
    pose_keypoints: list | None,  # 17-point array
)
```

### ClockCalibration
```python
ClockCalibration(
    id: UUID,
    session_id: UUID,
    calibrated_at: datetime,
    rtt_ms: float,  # Round-trip time
    offset_ms: float,  # device_ts offset
    quality: str,  # 'good' | 'acceptable' | 'poor'
)
```

### VideoSegment
```python
VideoSegment(
    id: UUID,
    session_id: UUID,
    file_path: str,
    start_frame: int,
    end_frame: int | None,
    capture_started_at: datetime | None,
    processed: bool = False,
)
```

---

## API Response Shapes

### Create Session
```json
POST /api/sessions
{
  "player_id": "uuid-or-null",
  "fps": 30.0
}

Returns:
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "player_id": null,
  "started_at": "2026-04-20T12:30:00.000000+00:00",
  "ended_at": null,
  "video_file_path": null,
  "fps": 30.0,
  "sync_quality": "none",
  "created_at": "2026-04-20T12:30:00.000000+00:00",
  "shot_count": 0
}
```

### Get Shot Statistics
```json
GET /api/sessions/{session_id}/shots/stats

Returns:
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "total_shots": 42,
  "distribution": [
    {
      "shot_type": "Forehand",
      "count": 18,
      "percentage": 42.857,
      "avg_confidence": 0.867,
      "max_confidence": 0.95,
      "min_confidence": 0.72
    },
    {
      "shot_type": "Smash",
      "count": 12,
      "percentage": 28.571,
      "avg_confidence": 0.89,
      "max_confidence": 0.98,
      "min_confidence": 0.81
    }
  ]
}
```

---

## WebSocket Protocol

### Incoming from ESP32 (SHOT_EVENT)
```json
{
  "type": "SHOT_EVENT",
  "shot_type": "Forehand",
  "confidence": 0.87,
  "device_ts_ms": 142350,
  "accel_x": 2.14,
  "accel_y": -0.87,
  "accel_z": 9.62,
  "gyro_x": 0.12,
  "gyro_y": -1.44,
  "gyro_z": 0.33
}
```

### Sync Exchange (Clock Calibration)
```json
Frontend → Backend (SYNC_PING):
{
  "type": "SYNC_PING",
  "browser_ts": 1713618600000
}

Backend → Frontend (SYNC_PONG):
{
  "type": "SYNC_PONG",
  "device_ts": 1713618600008,
  "echo_browser_ts": 1713618600000
}

RTT = 1713618608 - 1713618600000 = 8 ms
offset = 1713618600000 + 4 - 142350 = ...
```

### Broadcast to Connected Clients
```json
{
  "type": "SHOT_EVENT",
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "shot_type": "Forehand",
  "confidence": 0.87,
  "device_ts_ms": 142350,
  "timestamp": "2026-04-20T12:30:00.123Z"
}
```

---

## Database Queries (Common Patterns)

### Get all shots for a session
```python
shots = db.query(ShotEvent).filter(
    ShotEvent.session_id == session_id
).order_by(ShotEvent.device_ts_ms).all()
```

### Shot distribution by type
```python
stats = db.query(
    ShotEvent.shot_type,
    func.count(ShotEvent.id).label("count"),
    func.avg(ShotEvent.confidence).label("avg_conf")
).filter(
    ShotEvent.session_id == session_id
).group_by(ShotEvent.shot_type).all()
```

### Get latest calibration
```python
latest_cal = db.query(ClockCalibration).filter(
    ClockCalibration.session_id == session_id
).order_by(ClockCalibration.calibrated_at.desc()).first()
```

### Update shot with YOLO results
```python
shot = db.query(ShotEvent).get(shot_id)
shot.court_x = 0.42
shot.court_y = 0.58
shot.player_bbox = {"x": 100, "y": 200, "w": 50, "h": 100}
shot.pose_keypoints = [...]
db.commit()
```

---

## Dependency Injection Pattern

All routes use FastAPI dependency injection for DB access:

```python
from app.database import get_db
from sqlalchemy.orm import Session

def my_route(db: Session = Depends(get_db)):
    # db is automatically opened and closed per request
    result = db.query(ShotEvent).first()
    return result
```

---

## Environment Setup

Copy `.env.example` to `.env` and customize:

```bash
# Database
DATABASE_URL=postgresql://onyx:onyx@localhost:5432/onyx

# Server
ENV=development  # or 'production'
LOG_LEVEL=INFO

# CORS
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:5173
```

---

## Running Migrations

### Check status
```bash
alembic current
alembic history
```

### Apply pending
```bash
alembic upgrade head
```

### Create new migration (auto-detect model changes)
```bash
alembic revision --autogenerate -m "Add new field to ShotEvent"
```

### Rollback
```bash
alembic downgrade -1
```

---

## Starting the Server

### Development (with auto-reload)
```bash
cd backend
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Production
```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### Docker
```bash
docker-compose up --build
```

Access API docs at: **http://localhost:8000/docs**

---

## Common Errors & Fixes

| Error | Cause | Fix |
|-------|-------|-----|
| `CONNECTION REFUSED` | PostgreSQL not running | Start PostgreSQL service |
| `Could not find a match for alembic` | Missing alembic package | `pip install alembic` |
| `WebSocket connection refused` | API not running or wrong port | Verify `http://localhost:8000/health` works |
| `UNIQUE constraint violation` | Duplicate UUID | Check if record already exists before inserting |
| `asyncpg: server does not recognize session_id` | Typo in session UUID | Verify UUID format is valid |

---

## Testing Endpoints

### Create a session
```bash
curl -X POST http://localhost:8000/api/sessions \
  -H "Content-Type: application/json" \
  -d '{"fps": 30.0}'
```

### Get session stats
```bash
curl http://localhost:8000/api/sessions/{session_id}/shots/stats
```

### WebSocket test (using websocat)
```bash
websocat ws://localhost:8000/ws/shots/{session_id}

# Send sync ping:
{"type": "SYNC_PING", "browser_ts": 1713618600000}

# Receive pong:
{"type": "SYNC_PONG", "device_ts": 1713618600008, "echo_browser_ts": 1713618600000}
```

---

## Code Structure Notes

- **Models**: Define DB schema, used by SQLAlchemy ORM
- **Schemas**: Define API contract, used by Pydantic validation
- **Routers**: Handle HTTP/WebSocket requests, call DB via dependency injection
- **Config**: Centralized settings management
- **Database**: Engine setup, session factory, connection pooling

---

**Ready to extend?** See [BUILD_SUMMARY.md](BUILD_SUMMARY.md) for next steps (React frontend, ESP32 bridge, YOLO video processing).
