# 🚀 Local Development Setup (No Docker)

Run frontend and backend locally for testing.

## Prerequisites
- ✅ Python 3.14.2 (installed)
- ✅ Node.js 20+ (installed)
- ✅ PostgreSQL 16 (running locally)

---

## Quick Start (Two Terminals)

### Terminal 1: Frontend
```bash
cd e:\hardware\frontend
npm run dev
```
- Opens at http://localhost:5173
- Hot reload enabled
- Proxy to backend at http://localhost:8000

### Terminal 2: Backend
```bash
cd e:\hardware\backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```
- Runs at http://localhost:8000
- API Docs at http://localhost:8000/docs
- Hot reload enabled
- Connect to local PostgreSQL

---

## Database Setup (PostgreSQL)

### Windows (using WSL or local install):
```bash
# Ensure PostgreSQL is running
# Create database:
psql -U postgres -c "CREATE DATABASE onyx;"
psql -U postgres -c "CREATE USER onyx WITH PASSWORD 'onyx';"
psql -U postgres -c "ALTER ROLE onyx WITH CREATEDB;"

# Or if already exists:
psql -U onyx -d onyx -f /path/to/schema.sql
```

### Environment Variables

Create `.env` in `backend/` directory:
```
DATABASE_URL=postgresql://onyx:onyx@localhost:5432/onyx
ENV=development
LOG_LEVEL=DEBUG
ALLOWED_ORIGINS=http://localhost:5173,http://localhost:3000
```

Create `.env` in `frontend/` directory:
```
REACT_APP_API_URL=http://localhost:8000/api
```

---

## Step-by-Step Setup

### 1. Backend Setup
```bash
cd backend

# Create virtual environment
python -m venv venv

# Activate it
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run database migrations (if needed)
alembic upgrade head

# Start server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 2. Frontend Setup
```bash
cd frontend

# Dependencies already installed (npm install done)

# Start dev server
npm run dev
```

---

## Testing the System

### Frontend
- Visit http://localhost:5173
- Create a new session
- Watch real-time updates
- Check Console (F12) for WebSocket messages

### Backend API
- API Docs: http://localhost:8000/docs
- Try POST /api/sessions to create session
- Check WebSocket at ws://localhost:8000/ws/shots/{session_id}

### Database
```bash
# Connect to verify:
psql -U onyx -d onyx
\dt  # List tables
SELECT * FROM sessions;
```

---

## Troubleshooting

### Port Already in Use
```bash
# Find process on port 8000
netstat -ano | findstr :8000

# Kill process
taskkill /PID <PID> /F
```

### Database Connection Failed
1. Ensure PostgreSQL is running
2. Check credentials in .env
3. Verify DATABASE_URL format: `postgresql://user:password@host:port/dbname`

### Frontend Can't Connect to Backend
1. Ensure backend is running on 8000
2. Check REACT_APP_API_URL in .env or vite proxy
3. Check CORS in backend/app/main.py
4. Check browser console for errors

### Module Not Found (Python)
```bash
# Reinstall requirements
pip install -r requirements.txt --force-reinstall

# Or clear cache
pip cache purge
pip install -r requirements.txt
```

---

## Development Features

✅ **Frontend**
- Vite dev server with HMR
- TypeScript strict mode
- Tailwind CSS (no build step)
- React DevTools ready
- Network tab shows requests

✅ **Backend**
- Uvicorn auto-reload
- FastAPI Swagger UI (/docs)
- Request logging
- SQLAlchemy debug mode ready
- Alembic migrations available

✅ **WebSocket**
- Real-time shot events
- Clock sync protocol
- Auto-reconnect logic
- Live updates to dashboard

---

## Expected Output

### Frontend
```
  VITE v5.4.21  ready in 234 ms

  ➜  Local:   http://localhost:5173/
  ➜  press h to show help
```

### Backend
```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Started server process [12345]
INFO:     Application startup complete
```

---

## Next: Docker Deployment

Once testing is complete locally, deploy with:
```bash
docker-compose up --build
```

All three services (DB, Backend, Frontend) will start in containers with proper networking.

