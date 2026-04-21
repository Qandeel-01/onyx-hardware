# Quick Start Guide - Project ONYX

Get the entire system running in 5 minutes.

## Prerequisites Check

```bash
# Check Docker is installed
docker --version
docker-compose --version

# OR check Python/Node for local development
python --version   # Should be 3.11+
node --version    # Should be 18+
```

## Option 1: Docker Compose (RECOMMENDED)

### Step 1: Start Everything
```bash
cd e:\hardware
docker-compose up --build
```

**First run takes ~2 minutes** (pulling images, building)

### Step 2: Wait for Services
```
✓ PostgreSQL (port 5432)
✓ FastAPI Backend (port 8000)
✓ React Frontend (port 5173)
```

All services show health checks in output.

### Step 3: Access Dashboard
Open browser: **http://localhost:5173**

### Step 4: Create a Session
Click "Start Session" button (optionally enter player ID)

### Step 5: Test Real-Time Features
- Dashboard shows **🔴 Live Feed** status
- Charts are ready (will populate with shot data)
- WebSocket connection established automatically

### Step 6: Send Test Data (Optional)
```bash
# In a new terminal, simulate ESP32 shot
curl -X POST http://localhost:8000/api/sessions/{session_id}/shots \
  -H "Content-Type: application/json" \
  -d '{
    "shot_type": "Forehand",
    "confidence": 0.87,
    "device_ts": 1713607200,
    "accel_x": 2.14,
    "accel_y": 1.89,
    "accel_z": 0.92,
    "gyro_x": 0.45,
    "gyro_y": 0.23,
    "gyro_z": 0.12
  }'
```

---

## Option 2: Local Development

### Terminal 1: Start Database
```bash
# Using Docker
docker run --name onyx-db \
  -e POSTGRES_DB=onyx \
  -e POSTGRES_USER=onyx \
  -e POSTGRES_PASSWORD=onyx \
  -p 5432:5432 \
  postgres:16-alpine

# OR if PostgreSQL installed locally
psql -U postgres -c "CREATE DATABASE onyx;"
```

### Terminal 2: Start Backend
```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set database URL
export DATABASE_URL=postgresql://onyx:onyx@localhost:5432/onyx

# Run migrations
alembic upgrade head

# Start server
python -m uvicorn app.main:app --reload --port 8000
```

Backend running: http://localhost:8000

### Terminal 3: Start Frontend
```bash
cd frontend

# Install dependencies
npm install

# Start dev server
npm run dev
```

Frontend running: http://localhost:5173

---

## API Documentation

### Swagger UI (Interactive)
```
http://localhost:8000/docs
```

### Available Endpoints

**Create Session**
```bash
curl -X POST http://localhost:8000/api/sessions \
  -H "Content-Type: application/json" \
  -d '{"player_id": "player-123"}'
```

**Get Session**
```bash
curl http://localhost:8000/api/sessions/{session-id}
```

**Get Shots**
```bash
curl "http://localhost:8000/api/sessions/{session-id}/shots?skip=0&limit=100"
```

**Get Statistics**
```bash
curl http://localhost:8000/api/sessions/{session-id}/shots/stats
```

**WebSocket Connection**
```bash
# Using wscat (npm install -g wscat)
wscat -c ws://localhost:8000/ws/shots/{session-id}
```

---

## Testing the System

### Test REST Endpoints
```bash
# Create session
SESSION_ID=$(curl -s -X POST http://localhost:8000/api/sessions \
  -H "Content-Type: application/json" \
  -d '{}' | jq -r '.id')

echo "Created session: $SESSION_ID"

# Get session
curl http://localhost:8000/api/sessions/$SESSION_ID

# Get empty shots
curl "http://localhost:8000/api/sessions/$SESSION_ID/shots"

# Get stats
curl http://localhost:8000/api/sessions/$SESSION_ID/shots/stats
```

### Test WebSocket
```bash
# Terminal 1: Connect client
wscat -c ws://localhost:8000/ws/shots/$SESSION_ID

# In wscat terminal, type:
> {"type": "SYNC_PING", "timestamp": 1713607200000}

# You should receive:
< {"type": "SYNC_PONG", "offset_ms": 0, "quality": "good"}
```

### Test Frontend UI
1. Open http://localhost:5173
2. Click "Start Session"
3. Note the session ID
4. Open DevTools (F12)
5. Watch Network tab as WebSocket connects
6. See real-time updates

---

## Common Issues & Fixes

### Docker containers won't start
```bash
# See what went wrong
docker-compose logs -f

# Remove old containers
docker-compose down -v

# Try again
docker-compose up --build
```

### Database connection error
```bash
# Check if PostgreSQL is running
docker ps | grep onyx-db

# If using local PostgreSQL
psql -U onyx -d onyx -c "SELECT 1"

# Reset Docker PostgreSQL
docker-compose down -v
docker-compose up
```

### Frontend blank page
```bash
# Check API URL is correct
echo $REACT_APP_API_URL
# Should be: http://localhost:8000/api

# Check backend is running
curl http://localhost:8000/docs

# Clear browser cache (Ctrl+Shift+Delete)
```

### WebSocket won't connect
```bash
# Check WebSocket endpoint
curl -i http://localhost:8000/ws/shots/test

# Look for "101 Switching Protocols"
# If not, check backend logs

docker-compose logs onyx-api | grep -i websocket
```

### Port already in use
```bash
# Kill process on port 8000 (backend)
lsof -ti:8000 | xargs kill -9

# Kill process on port 5173 (frontend)
lsof -ti:5173 | xargs kill -9

# Kill process on port 5432 (database)
lsof -ti:5432 | xargs kill -9
```

---

## Stopping Services

### Docker Compose
```bash
# Stop all services
docker-compose down

# Stop and remove volumes (reset database)
docker-compose down -v
```

### Local Development
```bash
# Stop frontend (Ctrl+C in terminal)
# Stop backend (Ctrl+C in terminal)
# Stop database (Ctrl+C in terminal)
```

---

## File Structure

```
e:\hardware\
├── backend/               # FastAPI server
│   ├── app/
│   │   ├── main.py       # Entry point
│   │   ├── models/
│   │   ├── routers/
│   │   └── schemas.py
│   ├── migrations/        # Alembic database versions
│   ├── requirements.txt   # Python packages
│   └── Dockerfile
├── frontend/              # React dashboard
│   ├── src/
│   │   ├── App.tsx
│   │   ├── components/
│   │   ├── hooks/
│   │   ├── services/
│   │   └── types/
│   ├── package.json       # NPM packages
│   └── Dockerfile
├── docker-compose.yml     # Orchestration
├── README.md             # Full documentation
└── DEPLOYMENT.md         # Production guide
```

---

## Key URLs

| Service | URL | Notes |
|---------|-----|-------|
| Frontend | http://localhost:5173 | React dashboard |
| Backend API | http://localhost:8000 | FastAPI server |
| Swagger UI | http://localhost:8000/docs | API documentation |
| ReDoc | http://localhost:8000/redoc | Alternative API docs |
| Database | localhost:5432 | PostgreSQL (onyx/onyx) |

---

## Environment Variables

### Backend (docker-compose.yml)
```
DATABASE_URL: postgresql://onyx:onyx@db:5432/onyx
ENVIRONMENT: production
ALLOWED_ORIGINS: http://localhost:5173
```

### Frontend (.env)
```
REACT_APP_API_URL: http://localhost:8000/api
```

---

## Next Steps

1. ✅ System running (you are here)
2. Create test session in UI
3. Explore API documentation at `/docs`
4. Connect ESP32 device (see DEPLOYMENT.md)
5. Run live padel session
6. Deploy to production (see DEPLOYMENT.md)

---

## Need Help?

### Check Logs
```bash
# Backend logs
docker-compose logs onyx-api

# Frontend logs
docker-compose logs onyx-frontend

# Database logs
docker-compose logs onyx-db

# All logs
docker-compose logs -f
```

### Check Health
```bash
# Backend health
curl http://localhost:8000/health

# Frontend (should return HTML)
curl http://localhost:5173

# Database
psql -h localhost -U onyx -d onyx -c "SELECT version()"
```

### Review Documentation
- [Full Project Summary](PROJECT_SUMMARY.md)
- [Deployment Guide](DEPLOYMENT.md)
- [Backend README](backend/README.md)
- [Frontend README](frontend/README.md)

---

## Supported Platforms

- ✅ macOS (M1/Intel)
- ✅ Windows (Docker Desktop)
- ✅ Linux (any distribution)
- ✅ Cloud (AWS, GCP, Azure with Docker)

---

**🎉 You're ready to go!** Start with Option 1 (Docker Compose) for fastest setup.
