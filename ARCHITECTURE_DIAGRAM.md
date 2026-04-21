# System Architecture Diagram — Project ONYX Live Analysis

## 📐 High-Level Data Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        WEARABLE ESP32 DEVICE                            │
│                   (BNO055/MPU-6050 IMU Sensors)                        │
│                                                                         │
│    Detects shot: accel_xyz, gyro_xyz, ML classification               │
│    Output: { shot_type, confidence, device_ts_ms, accel/gyro }        │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
                    BLE / WiFi / UDP / REST POST
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    FASTAPI BACKEND (Port 8000)                          │
│                                                                         │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │ WebSocket: /ws/shots/{session_id}                               │  │
│  │  ├─ Receives: SHOT_EVENT, SYNC_PING                             │  │
│  │  ├─ Responds: SYNC_PONG                                         │  │
│  │  └─ Broadcasts: All connected clients                           │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                         │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │ REST API: /api/sessions/*                                       │  │
│  │  ├─ POST   /api/sessions                    (create)            │  │
│  │  ├─ GET    /api/sessions/{id}               (retrieve)          │  │
│  │  ├─ PATCH  /api/sessions/{id}               (update)            │  │
│  │  ├─ GET    /api/sessions/{id}/shots         (list shots)        │  │
│  │  ├─ GET    /api/sessions/{id}/shots/stats   (distribution)      │  │
│  │  ├─ POST   /api/sessions/{id}/calibrations  (sync record)       │  │
│  │  └─ GET    /api/sessions/{id}/calibrations  (sync history)      │  │
│  └──────────────────────────────────────────────────────────────────┘  │
└─────────────────┬──────────────────────────────────────┬────────────────┘
                  │                                      │
        Persistence / Sync Data              WebSocket Broadcast
                  │                                      │
                  ▼                                      ▼
         ┌────────────────┐              ┌──────────────────────────┐
         │  PostgreSQL    │              │   Browser Frontend       │
         │  (Port 5432)   │              │   (React Dashboard)      │
         │                │              │                          │
         │ ✓ sessions     │              │ ✓ Live shot timeline     │
         │ ✓ shot_events  │              │ ✓ Real-time charts      │
         │ ✓ calibrations │              │ ✓ Metrics dashboard      │
         │ ✓ video_segs   │              │ ✓ Clock sync UI          │
         └────────────────┘              └──────────────────────────┘
                  │                              │
                  └──────────────┬───────────────┘
                                 │
                    (Session data via REST API)
```

---

## 🔄 Clock Synchronization Flow

```
TIME T0: Frontend initiates sync
┌──────────────────────────────────────────────────────────┐
│ Frontend                          Backend                │
└──────────────────────────────────────────────────────────┘
    │
    │ { type: "SYNC_PING", browser_ts: T0.browser_ts }
    ├─────────────────────────────────────────────────────►
    │                                     Server receives at T0+RTT/2
    │                                     device_ts = now() = T0_server
    │
    │        { type: "SYNC_PONG",
    │          device_ts: T0_server,
    │          echo_browser_ts: T0.browser_ts }
    │◄─────────────────────────────────────────────────────
    │ Frontend receives at T2
    │
    ▼ RTT = T2 - T0.browser_ts
      one_way_latency = RTT / 2
      device_offset = T0.browser_ts + (RTT / 2) - T0_server

STORED: clock_offset_ms in ClockCalibration table
        quality = "good" (RTT < 5ms), "acceptable" (5-20ms), or "poor"

TIME T_SHOT: ESP32 detects shot
┌──────────────────────────────────────────────────────────┐
│ ESP32                 Backend                Frontend     │
└──────────────────────────────────────────────────────────┘
    │ device_ts_ms = 142350 (from millis())
    ├─────────────────────────────────────────────────────►
    │                       │ Compute:
    │                       │ wall_clock_ts = device_ts + offset
    │                       │ frame_index = floor(wall_clock_ts / frame_duration)
    │                       │
    │                       │ { type: "SHOT_EVENT", id, shot_type, ... }
    │                       ├─────────────────────────────►
    │                       │                       Dashboard updates in real-time
```

---

## 📦 Database Schema

```
┌──────────────────────────────────────────────────────────────────────┐
│                         SESSIONS TABLE                               │
│ ┌────────┬───────────┬────────────┬──────────┬──────────────────┐   │
│ │   id   │ player_id │ started_at │ ended_at │ sync_quality     │   │
│ │ (UUID) │  (UUID)   │ (DateTime) │(DateTime)│ 'none'|'est'|'cal'   │
│ └────────┴───────────┴────────────┴──────────┴──────────────────┘   │
└────┬─────────────────────────────────────────────────────────────────┘
     │ 1
     ├────────────┬────────────┬────────────┐
     │ N          │ N          │ N          │
     ▼            ▼            ▼            ▼
  SHOT_EVENTS  CLOCK_CAL  VIDEO_SEGMENTS
  ┌──────────┐  ┌──────┐   ┌────────────┐
  │ shot_type│  │ rtt_ │   │ file_path  │
  │confidence│  │ ms   │   │start_frame │
  │device_ts │  │offset│   │end_frame   │
  │wall_clock│  │qual  │   │capture_ts  │
  │accel_x/y │  └──────┘   │processed   │
  │accel_z   │             └────────────┘
  │gyro_x/y  │
  │gyro_z    │
  │court_x/y │ (post-YOLO)
  │player_box│ (post-YOLO)
  │pose_keys │ (post-YOLO)
  └──────────┘
```

---

## 🌐 API Request/Response Examples

### Create Session
```
REQUEST:
POST /api/sessions
Content-Type: application/json
{ "fps": 30.0, "player_id": null }

RESPONSE:
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "started_at": "2026-04-20T12:30:00Z",
  "fps": 30.0,
  "sync_quality": "none",
  "shot_count": 0
}
```

### Record Clock Calibration
```
REQUEST:
POST /api/sessions/{session_id}/calibrations?rtt_ms=8.5&offset_ms=42

RESPONSE:
{
  "id": "550e8400-e29b-41d4-a716-446655440001",
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "rtt_ms": 8.5,
  "offset_ms": 42,
  "quality": "good",
  "calibrated_at": "2026-04-20T12:30:05Z"
}
```

### Get Shot Stats
```
REQUEST:
GET /api/sessions/{session_id}/shots/stats

RESPONSE:
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "total_shots": 42,
  "distribution": [
    {
      "shot_type": "Forehand",
      "count": 18,
      "percentage": 42.86,
      "avg_confidence": 0.867,
      "max_confidence": 0.95,
      "min_confidence": 0.72
    },
    {
      "shot_type": "Smash",
      "count": 12,
      "percentage": 28.57,
      "avg_confidence": 0.89,
      ...
    }
  ]
}
```

---

## 🔌 WebSocket Message Protocol

### Outgoing (Frontend → Backend)

**Clock Sync Ping**:
```json
{
  "type": "SYNC_PING",
  "browser_ts": 1713618600000
}
```

### Incoming (Backend → Frontend)

**Clock Sync Pong**:
```json
{
  "type": "SYNC_PONG",
  "device_ts": 1713618600008,
  "echo_browser_ts": 1713618600000
}
```

**Shot Event Broadcast**:
```json
{
  "type": "SHOT_EVENT",
  "id": "550e8400-e29b-41d4-a716-446655440002",
  "shot_type": "Forehand",
  "confidence": 0.87,
  "device_ts_ms": 142350,
  "timestamp": "2026-04-20T12:30:00.123Z"
}
```

---

## 📂 File Organization

```
app/
├── main.py ────────────► FastAPI app, CORS, router mounting
├── config.py ──────────► Settings from env
├── database.py ────────► SQLAlchemy engine, SessionLocal
├── schemas.py ─────────► Pydantic models
├── models/
│   └── models.py ──────► SQLAlchemy ORM (4 tables)
└── routers/
    ├── sessions.py ────► REST endpoints (7 routes)
    └── ws_shots.py ────► WebSocket handler
```

---

## 🔄 Request Lifecycle Example: Receiving a Shot Event

```
1. ESP32 sends over BLE/WiFi
   ↓
   { "type": "SHOT_EVENT", "shot_type": "Forehand", "confidence": 0.87, ... }

2. Backend receives on WebSocket: /ws/shots/{session_id}
   ↓
   ws_shots.py::shot_stream() catches message

3. Parse & Validate
   ↓
   ShotEventCreate schema validates fields

4. Create ORM object & Save to DB
   ↓
   ShotEvent(session_id=..., shot_type=..., confidence=..., ...)
   db.add(shot_event)
   db.commit()

5. Broadcast to all connected clients
   ↓
   broadcast_to_session(session_id, {"type": "SHOT_EVENT", ...})

6. All listening frontends receive in real-time
   ↓
   Dashboard: Timeline updates, charts refresh, metrics update
```

---

## 🚀 Deployment Topology

```
Production Deployment:
┌───────────────────────────────────────────────────────┐
│ Docker Host / Kubernetes Pod                         │
│                                                       │
│ ┌─────────────────────────────────────────────────┐  │
│ │ Container: onyx-api (FastAPI)                   │  │
│ │ Image: backend:latest                           │  │
│ │ Port: 8000                                      │  │
│ │ Replicas: 2–4 (behind load balancer)            │  │
│ └─────────────────────────────────────────────────┘  │
│                       │                               │
│                       ▼                               │
│ ┌─────────────────────────────────────────────────┐  │
│ │ Container: onyx-db (PostgreSQL)                 │  │
│ │ Image: postgres:16-alpine                       │  │
│ │ Port: 5432                                      │  │
│ │ Volume: /var/lib/postgresql/data (persistent)   │  │
│ └─────────────────────────────────────────────────┘  │
│                                                       │
│ Network: onyx-network (bridge driver)                │
└───────────────────────────────────────────────────────┘
        │
        ├─ Exposed: api.onyx.local:8000
        └─ Exposed: db.onyx.local:5432 (internal only)
```

---

## 🧪 Local Development Stack

```
Machine (Windows/Mac/Linux)
│
├─ VSCode
│  └─ File editor, terminal
│
├─ PostgreSQL (running locally)
│  └─ psql -U onyx -h localhost
│
├─ Python venv (or docker)
│  ├─ FastAPI server (port 8000)
│  └─ alembic CLI
│
├─ Browser
│  ├─ http://localhost:8000/docs (Swagger API explorer)
│  └─ http://localhost:3000 (frontend, coming next)
│
└─ Terminal
   ├─ websocat ws://localhost:8000/ws/shots/{id}
   └─ curl, POST/GET requests
```

---

**Ready to integrate with React frontend!** See [INDEX.md](INDEX.md) for next steps.
