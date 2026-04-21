# Project ONYX - React Frontend

Real-time padel analytics dashboard with live shot analysis, IMU sensor visualization, and clock synchronization.

## Architecture

```
src/
├── main.tsx                 # Entry point
├── App.tsx                  # Root component with routing
├── index.css               # Global styles (Tailwind)
├── types/
│   └── index.ts           # TypeScript type definitions
├── services/
│   └── apiClient.ts       # REST API client for backend
├── hooks/
│   └── useShotWebSocket.ts # Custom hook for real-time WebSocket
├── components/
│   ├── SessionManager.tsx  # Session creation UI
│   ├── dashboard/
│   │   ├── LiveAnalysisDashboard.tsx  # Main dashboard container
│   │   ├── CameraPanel.tsx            # Video feed area
│   │   ├── ShotTimeline.tsx           # Chronological shot list
│   │   └── ShotStats.tsx              # KPI cards
│   └── charts/
│       ├── ShotDistributionChart.tsx  # Pie chart by shot type
│       ├── ShotRateChart.tsx          # Line chart over time
│       └── IMUIntensityChart.tsx      # Bar chart (accel/gyro)
```

## Components

### SessionManager
- Create new analysis sessions
- Optional player ID input
- Displays feature overview

### LiveAnalysisDashboard
- Real-time shot streaming via WebSocket
- Clock sync status indicator
- Session management controls
- Comprehensive data visualization

### CameraPanel
- Video feed display (live/recorded)
- Session metadata (FPS, quality, duration)
- Responsive video container

### ShotTimeline
- Reverse-chronological shot list
- Confidence level visualization
- IMU sensor data display
- Shot type color coding

### Chart Components
- **ShotDistributionChart**: Pie chart of shot type frequency
- **ShotRateChart**: Line chart showing shot rate + cumulative count
- **IMUIntensityChart**: Bar chart of acceleration/gyroscope magnitude

### KPI Cards (ShotStats)
- Total shot count
- Average confidence percentage
- Shot rate (shots/minute)
- Session duration

## WebSocket Protocol

### SYNC_PING (Client → Server)
```json
{
  "type": "SYNC_PING",
  "timestamp": 1713607200000
}
```

### SYNC_PONG (Server → Client)
```json
{
  "type": "SYNC_PONG",
  "timestamp": 1713607200050,
  "offset_ms": 12,
  "quality": "good"
}
```

### SHOT_EVENT (Server → Client)
```json
{
  "type": "SHOT_EVENT",
  "id": "uuid",
  "session_id": "uuid",
  "shot_type": "Forehand",
  "confidence": 0.87,
  "device_ts_ms": 142350,
  "accel_x": 2.14,
  "accel_y": 1.89,
  "accel_z": 0.92,
  "gyro_x": 0.45,
  "gyro_y": 0.23,
  "gyro_z": 0.12
}
```

## API Endpoints (via REST)

### Sessions
- `POST /api/sessions` - Create session
- `GET /api/sessions/{id}` - Get session details
- `PATCH /api/sessions/{id}` - Update session metadata

### Shots
- `GET /api/sessions/{id}/shots?skip=0&limit=100` - List shots
- `GET /api/sessions/{id}/shots/stats` - Get aggregated statistics

### Calibrations
- `POST /api/sessions/{id}/calibrations` - Record clock sync
- `GET /api/sessions/{id}/calibrations` - Get calibration history

## Setup & Running

### Prerequisites
- Node.js 18+
- Backend running on `http://localhost:8000`

### Installation
```bash
npm install
```

### Development
```bash
npm run dev
# Starts on http://localhost:5173
# Proxies /api/* to http://localhost:8000/api
# Proxies /ws/* to ws://localhost:8000/ws
```

### Build
```bash
npm run build
# Creates optimized production build in dist/
```

### Type Checking
```bash
npm run type-check
# Validates all TypeScript code
```

## Key Technologies

- **React 18**: UI framework
- **TypeScript**: Type-safe development
- **Vite**: Fast build tool
- **Tailwind CSS**: Utility-first styling
- **Recharts**: React charting library
- **Axios**: HTTP client
- **date-fns**: Date formatting utilities

## Styling

- **Colors**: Dark theme (slate/cyan/violet/emerald accents)
- **Layout**: Tailwind grid/flexbox responsive design
- **Animations**: Smooth transitions & loading states
- **Accessibility**: WCAG-compatible color contrasts

## WebSocket Connection Flow

1. Dashboard component mounts
2. `useShotWebSocket` hook establishes WebSocket connection
3. Client sends `SYNC_PING` to synchronize clocks
4. Server responds with `SYNC_PONG` (includes offset_ms)
5. Dashboard displays calibration status
6. Real-time `SHOT_EVENT` messages stream in
7. Charts & timeline update reactively
8. Connection maintained until component unmounts

## State Management

- React hooks (useState, useEffect, useRef)
- Custom `useShotWebSocket` hook for WebSocket management
- Props drilling for component communication
- Axios for HTTP request handling

## Performance Optimizations

- Lazy-loaded chart components
- Memoized socket message handlers
- Reverse-order timeline rendering (latest first)
- Limited IMU chart to last 20 shots
- Responsive grid layouts

## Environment Variables

Optional configuration in `.env`:
```
REACT_APP_API_URL=http://localhost:8000/api
```

Default: `http://localhost:8000/api`

## Integration with Backend

The frontend requires the FastAPI backend to be running with:
- REST API endpoints for session/shot CRUD
- WebSocket endpoint at `/ws/shots/{session_id}`
- Clock sync protocol (SYNC_PING/PONG)
- CORS headers allowing frontend domain

## Troubleshooting

**WebSocket Connection Failed**
- Ensure backend is running on port 8000
- Check browser console for connection errors
- Verify session_id is valid

**Charts Not Displaying**
- Ensure shot data has been received
- Check browser DevTools console for errors
- Verify Recharts types are installed

**Styling Issues**
- Clear Tailwind cache: `rm .tailwindcss`
- Rebuild with `npm run build`
- Check browser DevTools for CSS conflicts

## Next Steps

1. Deploy backend (Docker Compose)
2. Build React frontend (`npm run build`)
3. Serve static files from production server
4. Configure backend CORS for production domain
5. Connect ESP32 wearable to WebSocket
6. Run live padel sessions with real-time analytics
