# ESP32 + MPU6050 → ONYX backend

## What to configure

1. Install the **WebSockets** library by Markus Sattler in Arduino IDE (Library Manager).
2. Open `esp32_shot_client/esp32_shot_client.ino`.
3. Set `WIFI_SSID`, `WIFI_PASSWORD`, `BACKEND_HOST` (your PC or server LAN IP running FastAPI on port **8000**), and `SESSION_ID` (UUID from `POST http://<host>:8000/api/sessions`).
4. Flash to ESP32. The device connects to `ws://BACKEND_HOST:8000/ws/shots/<SESSION_ID>`.

## Message format

Send a **text** WebSocket frame with JSON:

```json
{
  "type": "SHOT_EVENT",
  "shot_type": "Forehand",
  "confidence": 0.85,
  "device_ts_ms": 1234567890,
  "accel_x": 0.1,
  "accel_y": 0.2,
  "accel_z": 9.8,
  "gyro_x": 0.0,
  "gyro_y": 0.0,
  "gyro_z": 0.0
}
```

`shot_type` must be one of: `Forehand`, `Backhand`, `Smash`, `Volley`, `Bandeja`, `Lob`.

## Stack on your PC

1. Start PostgreSQL (for example `docker compose up -d db` from the repo root; host port **5433** maps to the container).
2. Set `DATABASE_URL` in `backend/.env` to match (see `backend/.env.example`).
3. Run FastAPI: `cd backend && venv\\Scripts\\python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`.
4. Run the frontend with `VITE_ENABLE_WS=true` (see `frontend/.env.local`).
5. Create a session in the UI, copy its session id into the sketch, rebuild and flash.

The demo loop sends a shot every 5 seconds; replace that with your MPU6050 sampling and shot-detection logic.
