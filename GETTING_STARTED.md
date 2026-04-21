# 🚀 Getting Started — Project ONYX Live Analysis Backend

## Option 1: Docker Compose (Fastest — 2 minutes)

```bash
# Navigate to workspace
cd e:\hardware

# Start full stack (PostgreSQL + FastAPI)
docker-compose up --build

# Wait for logs showing:
# "Running migrations..."
# "Application startup complete"

# Access API docs
# http://localhost:8000/docs
```

**What happens**:
- PostgreSQL starts on port 5432
- FastAPI auto-runs migrations (creates schema)
- Backend starts on port 8000 with hot-reload
- Frontend placeholder (Node.js) starts on port 3000

**Verify**: Open http://localhost:8000/docs and click "Try it out" on any endpoint

---

## Option 2: Local Python Virtual Environment (5 minutes)

### Windows PowerShell
```powershell
# Create virtual environment
python -m venv backend\venv

# Activate it
backend\venv\Scripts\Activate.ps1

# Install dependencies
pip install -r backend\requirements.txt

# Run migrations (ensure PostgreSQL is running locally)
cd backend
alembic upgrade head

# Start server
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Mac/Linux Bash
```bash
# Create virtual environment
python3 -m venv backend/venv

# Activate it
source backend/venv/bin/activate

# Install dependencies
pip install -r backend/requirements.txt

# Run migrations
cd backend
alembic upgrade head

# Start server
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Access**: http://localhost:8000/docs

---

## Quick Test: Create a Session

### Using Swagger UI (GUI)
1. Go to http://localhost:8000/docs
2. Find **POST /api/sessions**
3. Click "Try it out"
4. Click "Execute"
5. See response with session UUID

### Using curl (Terminal)
```bash
curl -X POST http://localhost:8000/api/sessions \
  -H "Content-Type: application/json" \
  -d '{"fps": 30.0}'
```

**Expected Response**:
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "player_id": null,
  "started_at": "2026-04-20T12:30:00Z",
  "fps": 30.0,
  "sync_quality": "none",
  "shot_count": 0
}
```

---

## Test WebSocket Connection

### Using websocat
```bash
# Install (cargo required)
cargo install websocat

# Connect to WebSocket
websocat ws://localhost:8000/ws/shots/550e8400-e29b-41d4-a716-446655440000

# Send a sync ping
{"type": "SYNC_PING", "browser_ts": 1713618600000}

# Receive pong
{"type": "SYNC_PONG", "device_ts": 1713618600008, "echo_browser_ts": 1713618600000}

# Send a shot event
{"type": "SHOT_EVENT", "shot_type": "Forehand", "confidence": 0.87, "device_ts_ms": 142350, "accel_x": 2.14, "accel_y": -0.87, "accel_z": 9.62, "gyro_x": 0.12, "gyro_y": -1.44, "gyro_z": 0.33}

# See broadcast back
{"type": "SHOT_EVENT", "id": "uuid-here", "shot_type": "Forehand", "confidence": 0.87, ...}
```

---

## Common Commands

### Check if server is running
```bash
curl http://localhost:8000/health
# Returns: { "status": "healthy", "database": "connected", "environment": "development" }
```

### View API documentation
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### Run database migrations
```bash
cd backend
alembic upgrade head          # Apply pending migrations
alembic current               # Show current version
alembic history               # Show migration history
alembic downgrade -1          # Rollback one migration
```

### Connect to PostgreSQL directly
```bash
# Connection string
postgresql://onyx:onyx@localhost:5432/onyx

# Using psql
psql -U onyx -h localhost -d onyx

# View tables
\dt

# Query shots
SELECT shot_type, confidence, device_ts_ms FROM shot_events LIMIT 10;
```

### View server logs
```bash
# If running in terminal, you'll see logs in real-time
# If running in Docker:
docker logs onyx-api -f

# Filter for errors
docker logs onyx-api -f | grep ERROR
```

### Stop services
```bash
# Docker Compose
docker-compose down

# Keep PostgreSQL data
docker-compose down -v  # Remove volumes if needed

# Python venv (just Ctrl+C in terminal)
```

---

## Troubleshooting

### "Connection refused" on port 8000
```bash
# Check if server is running
curl http://localhost:8000/health

# If not:
# Docker: docker-compose up --build
# Local: python -m uvicorn app.main:app --reload
```

### "Cannot connect to database"
```bash
# Check PostgreSQL is running
# Docker: docker-compose ps (should show db is up)
# Local: psql -U onyx -h localhost (should work)

# Check connection string in .env
cat backend/.env | grep DATABASE_URL
```

### "WebSocket connection refused"
```bash
# Verify you're using ws:// not http://
# Verify session_id exists
curl http://localhost:8000/api/sessions

# Copy a session ID and try:
websocat ws://localhost:8000/ws/shots/{session_id}
```

### Migration errors
```bash
# Check current migration status
cd backend
alembic current

# Try upgrading again
alembic upgrade head

# Or reset (WARNING: deletes all data)
alembic downgrade base
alembic upgrade head
```

---

## File Structure Reference

```
e:\hardware\
├── backend/
│   ├── app/
│   │   ├── main.py              ← Start here for app code
│   │   ├── routers/
│   │   │   ├── sessions.py      ← REST endpoints
│   │   │   └── ws_shots.py      ← WebSocket
│   │   └── models/models.py     ← Database ORM
│   ├── requirements.txt          ← Dependencies
│   ├── .env                      ← Configuration (local dev)
│   └── README.md                 ← Setup guide
├── docker-compose.yml
├── INDEX.md                      ← Start here for navigation
├── BUILD_SUMMARY.md              ← What was built
└── QUICK_REFERENCE.md            ← Code examples
```

---

## Next Steps

1. **Start the server** (Docker or local)
2. **Create a session** via POST /api/sessions
3. **Connect WebSocket** to ws://localhost:8000/ws/shots/{session_id}
4. **Send test messages** to verify protocol
5. **Build React frontend** (Section 3 of spec) to connect and display data

---

## Resources

| Resource | Location |
|----------|----------|
| API Documentation | http://localhost:8000/docs |
| Setup Guide | [backend/README.md](backend/README.md) |
| Architecture | [ARCHITECTURE_DIAGRAM.md](ARCHITECTURE_DIAGRAM.md) |
| Code Reference | [QUICK_REFERENCE.md](QUICK_REFERENCE.md) |
| Spec Compliance | [IMPLEMENTATION_CHECKLIST.md](IMPLEMENTATION_CHECKLIST.md) |
| Overall Status | [COMPLETION_SUMMARY.md](COMPLETION_SUMMARY.md) |

---

## 🎯 Quick Verification Checklist

- [ ] Server starts (no errors in logs)
- [ ] http://localhost:8000/health returns 200
- [ ] http://localhost:8000/docs loads Swagger UI
- [ ] Can POST to /api/sessions and get UUID back
- [ ] Can GET /api/sessions/{id} and see session
- [ ] Can connect WebSocket without errors
- [ ] PostgreSQL has data in sessions table

**All checks passing?** ✅ Backend is working! Ready to build frontend.

---

**Questions?** See the detailed documentation files listed above, or check the terminal logs for error messages.
