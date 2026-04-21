# Project ONYX Live Analysis — FastAPI Backend

Real-time padel shot analysis backend with WebSocket support, clock synchronization, and wearable IoT integration.

## Architecture

- **FastAPI**: REST + WebSocket API
- **PostgreSQL**: Persistent data storage
- **SQLAlchemy**: ORM for database models
- **Alembic**: Database migrations
- **Docker Compose**: Multi-service orchestration

## Project Structure

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI app, routers
│   ├── config.py               # Environment configuration
│   ├── database.py             # SQLAlchemy setup
│   ├── schemas.py              # Pydantic models (request/response)
│   ├── models/
│   │   ├── __init__.py
│   │   └── models.py           # SQLAlchemy ORM models
│   └── routers/
│       ├── __init__.py
│       ├── sessions.py         # REST endpoints for sessions, shots, calibrations
│       └── ws_shots.py         # WebSocket endpoint for real-time events
├── alembic/
│   ├── env.py                  # Alembic environment config
│   ├── alembic.ini             # Alembic settings
│   ├── script.py.mako          # Migration template
│   └── versions/
│       └── 001_initial.py      # Initial schema migration
├── requirements.txt            # Python dependencies
├── Dockerfile                  # Container image
└── .env.example                # Example env vars
```

## Setup (Local Development)

### Prerequisites

- Python 3.11+
- PostgreSQL 16+
- Docker & Docker Compose (optional, for containerized setup)

### Option 1: Local Python Virtual Environment

```bash
# Create and activate venv
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up environment
cp .env.example .env
# Edit .env to set DATABASE_URL

# Create/migrate database
alembic upgrade head

# Run server
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Server will be available at `http://localhost:8000`.

### Option 2: Docker Compose (Full Stack)

```bash
# Start all services (db, api, frontend placeholder)
docker-compose up --build

# Run migrations (auto-runs on startup)
# Logs will show: "Running migrations..."
```

Access:
- **API**: `http://localhost:8000`
- **API Docs**: `http://localhost:8000/docs` (Swagger UI)
- **API ReDoc**: `http://localhost:8000/redoc`
- **Frontend**: `http://localhost:3000` (placeholder)
- **Database**: `localhost:5432` (user: `onyx`, password: `onyx`)

## Database Schema

### Sessions

```sql
CREATE TABLE sessions (
    id UUID PRIMARY KEY,
    player_id UUID,
    started_at TIMESTAMPTZ NOT NULL,
    ended_at TIMESTAMPTZ,
    video_file_path TEXT,
    fps FLOAT DEFAULT 30.0,
    sync_quality TEXT DEFAULT 'none',
    created_at TIMESTAMPTZ
);
```

### Shot Events

```sql
CREATE TABLE shot_events (
    id UUID PRIMARY KEY,
    session_id UUID REFERENCES sessions(id),
    shot_type TEXT NOT NULL,
    confidence FLOAT NOT NULL,
    device_ts_ms BIGINT NOT NULL,
    wall_clock_ts TIMESTAMPTZ,
    frame_index INTEGER,
    accel_x FLOAT, accel_y FLOAT, accel_z FLOAT,
    gyro_x FLOAT, gyro_y FLOAT, gyro_z FLOAT,
    court_x FLOAT, court_y FLOAT,
    player_bbox JSONB, pose_keypoints JSONB,
    created_at TIMESTAMPTZ
);
```

### Clock Calibrations

```sql
CREATE TABLE clock_calibrations (
    id UUID PRIMARY KEY,
    session_id UUID REFERENCES sessions(id),
    calibrated_at TIMESTAMPTZ NOT NULL,
    rtt_ms FLOAT NOT NULL,
    offset_ms FLOAT NOT NULL,
    quality TEXT NOT NULL,
);
```

### Video Segments

```sql
CREATE TABLE video_segments (
    id UUID PRIMARY KEY,
    session_id UUID REFERENCES sessions(id),
    file_path TEXT NOT NULL,
    start_frame INTEGER,
    end_frame INTEGER,
    capture_started_at TIMESTAMPTZ,
    processed BOOLEAN DEFAULT FALSE
);
```

## API Endpoints

### Sessions

**Create Session**
```
POST /api/sessions
Content-Type: application/json

{
  "player_id": "uuid",
  "fps": 30.0
}

Response: { id, started_at, ... }
```

**Get Session**
```
GET /api/sessions/{session_id}

Response: { id, started_at, ended_at, shot_count, ... }
```

**Update Session**
```
PATCH /api/sessions/{session_id}
Content-Type: application/json

{
  "ended_at": "2026-04-20T12:30:00Z",
  "video_file_path": "s3://bucket/video.mp4",
  "sync_quality": "calibrated"
}
```

**Get Session Shots**
```
GET /api/sessions/{session_id}/shots?skip=0&limit=100

Response: [{ id, shot_type, confidence, device_ts, ... }, ...]
```

**Get Shot Statistics**
```
GET /api/sessions/{session_id}/shots/stats

Response: {
  "total_shots": 42,
  "distribution": [
    {
      "shot_type": "Forehand",
      "count": 18,
      "percentage": 42.9,
      "avg_confidence": 0.87,
      "max_confidence": 0.95,
      "min_confidence": 0.72
    },
    ...
  ]
}
```

**Create Clock Calibration**
```
POST /api/sessions/{session_id}/calibrations?rtt_ms=8.5&offset_ms=42

Response: { id, session_id, calibrated_at, rtt_ms, offset_ms, quality }
```

**Get Calibrations**
```
GET /api/sessions/{session_id}/calibrations

Response: [{ id, rtt_ms, offset_ms, quality, ... }, ...]
```

### WebSocket

**Shot Event Stream & Sync**
```
WebSocket: ws://localhost:8000/ws/shots/{session_id}

Incoming (from ESP32):
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

Clock Sync (from Frontend):
{
  "type": "SYNC_PING",
  "browser_ts": 1713618600000
}

Response:
{
  "type": "SYNC_PONG",
  "device_ts": 1713618600008,
  "echo_browser_ts": 1713618600000
}

Broadcast to Frontend:
{
  "type": "SHOT_EVENT",
  "id": "uuid",
  "shot_type": "Forehand",
  "confidence": 0.87,
  "device_ts_ms": 142350,
  "timestamp": "2026-04-20T12:30:00.123Z"
}
```

## Running Migrations

### Create a new migration

```bash
alembic revision --autogenerate -m "Description of changes"
```

### Apply pending migrations

```bash
alembic upgrade head
```

### Rollback one migration

```bash
alembic downgrade -1
```

### View migration history

```bash
alembic history
```

## Development Notes

- **CORS**: Configured to allow `localhost:3000` and `localhost:5173` (Vite). Update in `config.py` for production.
- **Database URL**: Set via `.env` file. Default: `postgresql://onyx:onyx@localhost:5432/onyx`
- **Hot Reload**: Enabled in dev mode (`uvicorn --reload`)
- **Logging**: All WebSocket events, schema operations logged at INFO level
- **Error Handling**: Validation errors return HTTP 422; missing resources return 404

## Testing WebSocket Connection

Use `websocat` or similar:

```bash
# Install websocat
cargo install websocat

# Connect to WebSocket
websocat ws://localhost:8000/ws/shots/{session_id}

# Send a shot event
{"type": "SHOT_EVENT", "shot_type": "Forehand", "confidence": 0.87, "device_ts_ms": 100000, ...}

# Send sync ping
{"type": "SYNC_PING", "browser_ts": 1713618600000}
```

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `postgresql://onyx:onyx@localhost:5432/onyx` | PostgreSQL connection string |
| `ENV` | `development` | Environment mode: `development` or `production` |
| `LOG_LEVEL` | `INFO` | Logging verbosity |
| `ALLOWED_ORIGINS` | `http://localhost:3000,http://localhost:5173` | CORS allowed origins (comma-separated) |

## Troubleshooting

**Cannot connect to database:**
- Ensure PostgreSQL is running and accessible
- Check `DATABASE_URL` in `.env`
- Verify credentials match

**WebSocket connection refused:**
- Ensure API is running on port 8000
- Check firewall rules
- Verify session exists before connecting

**Migrations fail:**
- Check Alembic version: `alembic current`
- Review migration scripts in `alembic/versions/`
- Run `alembic stamp head` if migrations are out of sync

---

**Next Steps**: Connect React frontend with WebSocket hook, implement video processing pipeline, add pose-based form analysis.
