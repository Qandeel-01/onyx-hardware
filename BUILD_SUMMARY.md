# FastAPI Backend Build Summary

## ✅ Completed

### 1. Project Structure
- **backend/** directory with organized subdirectories:
  - `app/` — Main application package
  - `alembic/` — Database migration management
  - `app/models/` — SQLAlchemy ORM models
  - `app/routers/` — API endpoint handlers
  - `app/schemas.py` — Pydantic validation schemas

### 2. Configuration & Database
- **config.py**: Environment variables management (DATABASE_URL, ENV, LOG_LEVEL, CORS origins)
- **database.py**: SQLAlchemy engine, session factory, async context manager
- **.env** & **.env.example**: Pre-configured for local PostgreSQL (`postgresql://onyx:onyx@localhost:5432/onyx`)

### 3. SQLAlchemy ORM Models (`models/models.py`)
Four core tables fully defined with relationships:
- **Session**: padel analysis session with fps, sync_quality, video_file_path
- **ShotEvent**: wearable shot events (shot_type, confidence, device_ts_ms, accel/gyro, post-processing fields)
- **ClockCalibration**: clock sync calibration events (rtt_ms, offset_ms, quality tier)
- **VideoSegment**: recorded video metadata (file_path, frame range, capture timestamp)

### 4. Database Migrations (Alembic)
- **alembic/env.py**: Configured to auto-load models and apply migrations
- **alembic/versions/001_initial.py**: Complete schema creation with:
  - All 4 tables with correct column types (UUID, DateTime, JSONB, BigInteger, etc.)
  - Foreign key constraints with CASCADE delete
  - Composite indexes on session_id + device_ts_ms for query optimization
  - PostgreSQL JSONB support for player_bbox and pose_keypoints

### 5. Pydantic Schemas (`schemas.py`)
Request/response models for validation:
- `ShotEventCreate`, `ShotEventResponse`
- `SessionCreate`, `SessionUpdate`, `SessionResponse`
- `ClockCalibrationCreate`, `ClockCalibrationResponse`
- `SyncPingMessage`, `SyncPongMessage` (WebSocket)
- `ShotType` enum (Forehand, Backhand, Smash, Volley, Bandeja, Lob)

### 6. REST API Endpoints (`routers/sessions.py`)
Complete CRUD operations:
- **POST /api/sessions** → Create new session, returns UUID
- **GET /api/sessions/{id}** → Retrieve session + shot count
- **PATCH /api/sessions/{id}** → Update ended_at, video_file_path, sync_quality
- **GET /api/sessions/{id}/shots** → List all shots (pagination: skip/limit)
- **GET /api/sessions/{id}/shots/stats** → Shot distribution by type, avg/max/min confidence
- **POST /api/sessions/{id}/calibrations** → Record clock calibration
- **GET /api/sessions/{id}/calibrations** → Retrieve all calibration events

All endpoints include:
- Full error handling (404 on missing sessions)
- Query parameters for pagination
- Database transaction management
- Info-level logging

### 7. WebSocket Endpoint (`routers/ws_shots.py`)
Real-time event streaming:
- **Connection**: `/ws/shots/{session_id}` accepts WebSocket upgrades
- **SYNC_PING/PONG**: Bidirectional clock synchronization handshake
  - Client sends: `{ type: "SYNC_PING", browser_ts: timestamp }`
  - Server responds: `{ type: "SYNC_PONG", device_ts: timestamp, echo_browser_ts: ... }`
- **SHOT_EVENT**: Receives shot events from ESP32, persists to DB, broadcasts to all listeners
  - Validates shot_type, confidence (0–1), accel/gyro fields
  - Auto-saves to shot_events table with transaction commit
  - Broadcasts to all connected WebSocket clients on same session
- **Connection Management**: Tracks active connections per session_id, cleans up on disconnect
- **Error Handling**: Graceful handling of malformed messages, connection drops

### 8. Main FastAPI App (`app/main.py`)
- Auto-creates database tables on startup (via `Base.metadata.create_all`)
- Configures CORS middleware (allows localhost:3000, localhost:5173)
- Mounts both REST and WebSocket routers
- Health check endpoints: `GET /` and `GET /health`
- Proper error logging

### 9. Docker Support
- **Dockerfile**: Multi-stage build with:
  - Python 3.11-slim base image
  - System dependencies (gcc, postgres-client)
  - Health check against `/health` endpoint
  - Uvicorn server on port 8000
  
- **docker-compose.yml**: Full stack orchestration:
  - **db**: PostgreSQL 16 Alpine with persistent volume
  - **api**: FastAPI backend with auto-migration on startup
  - **frontend**: Node.js placeholder for future React integration
  - Shared `onyx-network` bridge
  - Service dependencies and health checks

### 10. Documentation
- **README.md**: Complete setup guide with:
  - Architecture overview
  - Local dev setup (venv + docker-compose)
  - Full schema documentation
  - API endpoint reference with examples
  - WebSocket protocol specification
  - Migration commands
  - Troubleshooting guide

---

## 📊 What's Ready

| Component | Status | Details |
|-----------|--------|---------|
| Database Schema | ✅ | 4 tables, indexes, FK constraints |
| ORM Models | ✅ | SQLAlchemy with relationships |
| Migrations | ✅ | Alembic v001 ready to apply |
| WebSocket | ✅ | Sync ping/pong, shot broadcasting |
| REST API | ✅ | Sessions, shots, stats, calibrations |
| Docker | ✅ | Compose stack with PostgreSQL |
| Config | ✅ | .env-based, CORS configured |
| Logging | ✅ | INFO-level events for all operations |

---

## 🚀 Quick Start

### Local Development (No Docker)
```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
alembic upgrade head  # Create schema in PostgreSQL
python -m uvicorn app.main:app --reload
```
Access: http://localhost:8000/docs

### Full Stack (Docker Compose)
```bash
docker-compose up --build
```
Auto-runs migrations. Access: http://localhost:8000/docs

---

## 🔄 Data Flow Example

1. **Frontend connects to WebSocket**:
   ```
   → WebSocket: ws://localhost:8000/ws/shots/{session_id}
   ```

2. **Frontend sends sync ping**:
   ```json
   { "type": "SYNC_PING", "browser_ts": 1713618600000 }
   ```

3. **Backend responds with server time**:
   ```json
   { "type": "SYNC_PONG", "device_ts": 1713618600008, "echo_browser_ts": 1713618600000 }
   ```

4. **ESP32 sends shot event** (via WiFi bridge):
   ```json
   {
     "type": "SHOT_EVENT",
     "shot_type": "Forehand",
     "confidence": 0.87,
     "device_ts_ms": 142350,
     "accel_x": 2.14, "accel_y": -0.87, "accel_z": 9.62,
     "gyro_x": 0.12, "gyro_y": -1.44, "gyro_z": 0.33
   }
   ```

5. **Backend persists to database** and broadcasts:
   ```json
   {
     "type": "SHOT_EVENT",
     "id": "uuid-12345",
     "shot_type": "Forehand",
     "confidence": 0.87,
     "device_ts_ms": 142350,
     "timestamp": "2026-04-20T12:30:00.123Z"
   }
   ```

6. **Frontend receives broadcast** and updates dashboard in real-time

---

## 📦 Files Created

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py                 (FastAPI app)
│   ├── config.py               (settings)
│   ├── database.py             (SQLAlchemy)
│   ├── schemas.py              (Pydantic)
│   ├── models/
│   │   ├── __init__.py
│   │   └── models.py           (ORM)
│   └── routers/
│       ├── __init__.py
│       ├── sessions.py         (REST)
│       └── ws_shots.py         (WebSocket)
├── alembic/
│   ├── env.py
│   ├── alembic.ini
│   ├── script.py.mako
│   └── versions/
│       └── 001_initial.py      (migration)
├── requirements.txt
├── Dockerfile
├── .env
├── .env.example
├── .gitignore
└── README.md

docker-compose.yml
```

---

## ✨ Highlights

✅ **Production-ready**: Error handling, logging, transactions, CORS  
✅ **Type-safe**: Full Pydantic validation + SQLAlchemy typing  
✅ **Scalable**: Connection pooling, index optimization, async-ready  
✅ **Documented**: Comprehensive README + inline comments  
✅ **Testable**: Dependency injection pattern for DB sessions  
✅ **Containerized**: Docker setup with health checks  

---

## 🔜 Next Steps (Per Spec)

1. **React Frontend** → Build Live Analysis Dashboard (Section 3 of spec)
2. **ESP32 Bridge** → Python service to forward BLE/WiFi → WebSocket
3. **Video Processing** → YOLO inference pipeline + frame linking
4. **Court Homography** → 2D court overlay with shot location mapping
5. **Session Export** → CSV/PDF generation with stats

