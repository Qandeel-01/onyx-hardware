# Deployment Guide - Project ONYX

Complete guide for deploying the full Project ONYX stack (backend + frontend).

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    ESP32 Wearable Device                    │
│                  (BLE/WiFi → WebSocket)                      │
└────────────────────────────┬────────────────────────────────┘
                             │
            ┌────────────────┼────────────────┐
            │                │                │
    ┌──────▼────────┐ ┌─────▼──────┐ ┌──────▼─────────┐
    │  REST Client  │ │ WebSocket  │ │  Video Stream  │
    │   (Sessions)  │ │ (Real-time)│ │    (Optional)  │
    └──────┬────────┘ └─────┬──────┘ └──────┬─────────┘
           │                │               │
    ┌──────┴────────────────┼───────────────┴──────┐
    │                       │                      │
    │          FastAPI Backend (Port 8000)         │
    │  ┌─────────────────────────────────────────┐ │
    │  │  SQLAlchemy ORM → PostgreSQL Database   │ │
    │  │  Endpoints:                             │ │
    │  │  - REST: /api/sessions, /api/shots     │ │
    │  │  - WebSocket: /ws/shots/{session_id}   │ │
    │  └─────────────────────────────────────────┘ │
    └──────────────┬───────────────────────────────┘
                   │
    ┌──────────────┴───────────────┐
    │                              │
┌───▼──────────────┐      ┌────────▼─────────┐
│ React Frontend   │      │ PostgreSQL 16    │
│ (Port 5173)      │      │ (Port 5432)      │
│                  │      │                  │
│ Dashboard with:  │      │ Tables:          │
│ - Live charts    │      │ - sessions       │
│ - Shot timeline  │      │ - shot_events    │
│ - Real-time data │      │ - calibrations   │
│ - Camera feed    │      │ - video_segments │
└──────────────────┘      └──────────────────┘
```

## Local Development

### Prerequisites
- Python 3.11+
- Node.js 18+
- PostgreSQL 16+
- Docker & Docker Compose (optional)

### Step 1: Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up database
export DATABASE_URL=postgresql://user:password@localhost:5432/onyx_dev
alembic upgrade head

# Start backend server
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Backend runs at: http://localhost:8000
Swagger docs: http://localhost:8000/docs

### Step 2: Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

Frontend runs at: http://localhost:5173

### Step 3: Database Setup

```bash
# Install PostgreSQL (macOS with Homebrew)
brew install postgresql

# Start PostgreSQL
brew services start postgresql

# Create database
createdb onyx_dev

# Set connection string
export DATABASE_URL=postgresql://$(whoami)@localhost:5432/onyx_dev
```

### Step 4: Run System

1. Terminal 1: Start PostgreSQL (if not using Docker)
2. Terminal 2: Start backend (`python -m uvicorn app.main:app --reload`)
3. Terminal 3: Start frontend (`npm run dev`)
4. Open http://localhost:5173 in browser

## Docker Deployment

### Single-Machine Docker Compose

```bash
# From project root
docker-compose up --build

# Services started:
# - Backend: http://localhost:8000
# - Frontend: http://localhost:5173
# - PostgreSQL: localhost:5432 (internal network)
# - pgAdmin (optional): http://localhost:5050
```

### Production Build

```bash
# Build images
docker-compose build

# Run with production settings
docker-compose -f docker-compose.yml up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

## Cloud Deployment (AWS Example)

### Using ECS (Elastic Container Service)

1. **Push images to ECR (Elastic Container Registry)**
   ```bash
   aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin [ACCOUNT_ID].dkr.ecr.us-east-1.amazonaws.com
   
   docker tag onyx-backend:latest [ACCOUNT_ID].dkr.ecr.us-east-1.amazonaws.com/onyx-backend:latest
   docker push [ACCOUNT_ID].dkr.ecr.us-east-1.amazonaws.com/onyx-backend:latest
   
   docker tag onyx-frontend:latest [ACCOUNT_ID].dkr.ecr.us-east-1.amazonaws.com/onyx-frontend:latest
   docker push [ACCOUNT_ID].dkr.ecr.us-east-1.amazonaws.com/onyx-frontend:latest
   ```

2. **Create RDS PostgreSQL instance**
   - Engine: PostgreSQL 16
   - Instance: db.t3.micro (or larger)
   - Backup retention: 7 days
   - Multi-AZ: Enabled for production

3. **Create ECS Cluster**
   - Capacity provider: FARGATE or EC2
   - Security groups: Allow 8000 (backend), 5173 (frontend), 5432 (DB)

4. **Deploy Backend Task**
   - Image: ECR backend image
   - Port: 8000
   - Environment: DATABASE_URL pointing to RDS
   - Memory: 512 MB
   - CPU: 256

5. **Deploy Frontend Task**
   - Image: ECR frontend image
   - Port: 5173
   - Environment: REACT_APP_API_URL=http://backend:8000/api
   - Memory: 256 MB
   - CPU: 128

6. **Set up ALB (Application Load Balancer)**
   - Target group for backend: /api/* → port 8000
   - Target group for frontend: /* → port 5173
   - HTTPS certificate: Use AWS Certificate Manager

### Using Kubernetes (EKS)

```yaml
# backend-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: onyx-backend
spec:
  replicas: 2
  selector:
    matchLabels:
      app: onyx-backend
  template:
    metadata:
      labels:
        app: onyx-backend
    spec:
      containers:
      - name: backend
        image: [ACCOUNT_ID].dkr.ecr.us-east-1.amazonaws.com/onyx-backend:latest
        ports:
        - containerPort: 8000
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: db-secrets
              key: url
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "1Gi"
            cpu: "1000m"

---
apiVersion: v1
kind: Service
metadata:
  name: onyx-backend
spec:
  type: ClusterIP
  ports:
  - port: 8000
    targetPort: 8000
  selector:
    app: onyx-backend
```

Deploy with:
```bash
kubectl apply -f backend-deployment.yaml
kubectl apply -f frontend-deployment.yaml
kubectl apply -f ingress.yaml
```

## Environment Variables

### Backend (.env or docker-compose.yml)
```
DATABASE_URL=postgresql://user:password@localhost:5432/onyx_prod
ENVIRONMENT=production
CORS_ORIGINS=["https://yourdomain.com"]
LOG_LEVEL=INFO
```

### Frontend (.env.production)
```
REACT_APP_API_URL=https://api.yourdomain.com
REACT_APP_WS_URL=wss://api.yourdomain.com
```

## SSL/HTTPS Configuration

### Using nginx Reverse Proxy

```nginx
upstream backend {
    server localhost:8000;
}

upstream frontend {
    server localhost:5173;
}

server {
    listen 443 ssl http2;
    server_name yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;

    location /api {
        proxy_pass http://backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /ws {
        proxy_pass http://backend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    location / {
        proxy_pass http://frontend;
        proxy_set_header Host $host;
    }
}

server {
    listen 80;
    server_name yourdomain.com;
    return 301 https://$server_name$request_uri;
}
```

## Monitoring & Logging

### Application Monitoring
- **Backend logs**: `docker logs onyx-backend`
- **Frontend logs**: Browser console + network tab
- **Database logs**: `docker logs onyx-db`

### Health Checks
```bash
# Backend health
curl http://localhost:8000/health

# Frontend
curl http://localhost:5173/

# Database
psql postgresql://user:password@localhost:5432/onyx_prod -c "SELECT 1"
```

### Metrics Collection (Optional)
Add Prometheus/Grafana:
```bash
docker run -p 9090:9090 prom/prometheus --config.file=/etc/prometheus/prometheus.yml
docker run -p 3000:3000 grafana/grafana
```

## Backup & Recovery

### Database Backup
```bash
# Manual backup
pg_dump postgresql://user:password@localhost:5432/onyx_prod > backup.sql

# Automated with cron
0 2 * * * pg_dump $DATABASE_URL | gzip > /backups/onyx_$(date +\%Y\%m\%d).sql.gz

# Restore
psql postgresql://user:password@localhost:5432/onyx_prod < backup.sql
```

### Video File Backup
- Configure S3 bucket for video storage
- Set lifecycle policies for retention
- Use CloudFront for CDN distribution

## Performance Tuning

### Backend Optimization
```python
# In app/main.py
from fastapi_limiter import FastAPILimiter

# Add rate limiting
@limiter.limit("100/minute")
async def get_shots():
    ...
```

### Database Optimization
```sql
-- Create indexes for common queries
CREATE INDEX idx_session_shots ON shot_events(session_id, device_ts_ms);
CREATE INDEX idx_calibration_session ON clock_calibrations(session_id);

-- Vacuum and analyze regularly
VACUUM ANALYZE;
```

### Frontend Optimization
```bash
npm run build  # Generates optimized production build

# Enable gzip compression in nginx
gzip on;
gzip_types application/javascript text/css;
gzip_min_length 1000;
```

## Troubleshooting Deployment

### Backend not connecting to database
```bash
# Check connection string format
psql $DATABASE_URL -c "SELECT 1"

# Check firewall/security groups
telnet localhost 5432
```

### Frontend can't reach API
```bash
# Check API URL configuration
echo $REACT_APP_API_URL

# Check backend is running
curl http://localhost:8000/docs

# Check CORS headers
curl -i http://localhost:8000/api/sessions
```

### WebSocket connection fails
```bash
# Check WebSocket proxy in nginx
# Ensure Upgrade/Connection headers are set

# Test WebSocket connection
wscat -c ws://localhost:8000/ws/shots/test
```

## Production Checklist

- [ ] Database backups automated
- [ ] SSL certificates configured
- [ ] Environment variables set correctly
- [ ] Rate limiting enabled
- [ ] Logging aggregation configured
- [ ] Health checks operational
- [ ] Load balancer configured
- [ ] Error monitoring (Sentry/Rollbar) enabled
- [ ] Performance monitoring (NewRelic/DataDog) enabled
- [ ] Disaster recovery plan documented
- [ ] User authentication implemented
- [ ] API documentation updated
