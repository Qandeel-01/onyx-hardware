#!/usr/bin/env python3
"""
Simple Mock Backend Server for Local Frontend Testing
Provides basic API endpoints without database or complex dependencies
"""

import json
import time
import uuid
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread
from urllib.parse import urlparse
import random

# Mock data storage
mock_sessions: dict[str, dict] = {}
mock_shots: dict[str, list[dict]] = {}
mock_calibrations: dict[str, list[dict]] = {}


def _iso_now() -> str:
    return datetime.now().isoformat()


def _read_json(handler: BaseHTTPRequestHandler) -> dict:
    content_length = int(handler.headers.get("Content-Length", 0))
    if content_length <= 0:
        return {}
    raw = handler.rfile.read(content_length)
    if not raw:
        return {}
    return json.loads(raw)


def _send_json(handler: BaseHTTPRequestHandler, payload, status: int = 200) -> None:
    body = json.dumps(payload).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Methods", "GET, POST, PATCH, PUT, DELETE, OPTIONS")
    handler.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _compute_stats(session_id: str) -> dict:
    shots = mock_shots.get(session_id, [])
    total = len(shots)
    if total == 0:
        return {
            "total_shots": 0,
            "distribution": [],
            "avg_confidence": 0,
            "earliest_ts": 0,
            "latest_ts": 0,
        }

    confidences = [float(s.get("confidence", 0)) for s in shots]
    device_ts = [int(s.get("device_ts", 0)) for s in shots if s.get("device_ts") is not None]
    earliest_ts = min(device_ts) if device_ts else 0
    latest_ts = max(device_ts) if device_ts else 0
    avg_conf = sum(confidences) / total

    # Group by shot_type
    dist_map: dict[str, list[float]] = {}
    for s in shots:
        st = str(s.get("shot_type", "Forehand"))
        dist_map.setdefault(st, []).append(float(s.get("confidence", 0)))

    distribution = []
    for shot_type, confs in dist_map.items():
        distribution.append(
            {
                "shot_type": shot_type,
                "count": len(confs),
                "avg_confidence": sum(confs) / len(confs) if confs else 0,
                "max_confidence": max(confs) if confs else 0,
                "min_confidence": min(confs) if confs else 0,
            }
        )

    return {
        "total_shots": total,
        "distribution": distribution,
        "avg_confidence": avg_conf,
        "earliest_ts": earliest_ts,
        "latest_ts": latest_ts,
    }


_SHOT_TYPES = ["Forehand", "Backhand", "Smash", "Volley", "Bandeja", "Lob"]


def _generate_shot(session_id: str, overrides: dict | None = None) -> dict:
    now_iso = _iso_now()
    device_ts = int(time.time() * 1000)
    shot_type = random.choice(_SHOT_TYPES)
    confidence = round(random.uniform(0.55, 0.98), 3)

    shot = {
        "id": str(uuid.uuid4()),
        "session_id": session_id,
        "shot_type": shot_type,
        "confidence": confidence,
        "device_ts": device_ts,
        "wall_clock_ts": now_iso,
        # Basic IMU fields used by the IMU chart.
        "accel_x": round(random.uniform(-25, 25), 3),
        "accel_y": round(random.uniform(-25, 25), 3),
        "accel_z": round(random.uniform(-25, 25), 3),
        "gyro_x": round(random.uniform(-500, 500), 3),
        "gyro_y": round(random.uniform(-500, 500), 3),
        "gyro_z": round(random.uniform(-500, 500), 3),
        "created_at": now_iso,
    }

    if overrides and isinstance(overrides, dict):
        # Only apply known keys to keep the shape consistent.
        for key in (
            "shot_type",
            "confidence",
            "device_ts",
            "wall_clock_ts",
            "accel_x",
            "accel_y",
            "accel_z",
            "gyro_x",
            "gyro_y",
            "gyro_z",
            "frame_index",
            "court_x",
            "court_y",
        ):
            if key in overrides:
                shot[key] = overrides[key]

    return shot


class ReusableHTTPServer(HTTPServer):
    allow_reuse_address = True

class APIHandler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        """Handle CORS preflight"""
        _send_json(self, {}, status=200)

    def do_GET(self):
        """Handle GET requests"""
        path = urlparse(self.path).path

        if path in ("/", "/health"):
            return _send_json(self, {"status": "ok"})

        if path == "/docs":
            return _send_json(self, {"info": "ONYX Mock API", "base": "/api"})

        if path == "/api/sessions":
            # Return an array for convenience.
            return _send_json(self, list(mock_sessions.values()))

        if path.startswith("/api/sessions/"):
            parts = path.split("/")
            # /api/sessions/{id}
            if len(parts) == 4:
                session_id = parts[3]
                session = mock_sessions.get(session_id)
                if not session:
                    return _send_json(self, {"error": "session not found"}, status=404)
                return _send_json(self, session)

            # /api/sessions/{id}/shots
            if len(parts) == 5 and parts[4] == "shots":
                session_id = parts[3]
                return _send_json(self, mock_shots.get(session_id, []))

            # /api/sessions/{id}/shots/stats
            if len(parts) == 6 and parts[4] == "shots" and parts[5] == "stats":
                session_id = parts[3]
                return _send_json(self, _compute_stats(session_id))

            # /api/sessions/{id}/calibrations
            if len(parts) == 5 and parts[4] == "calibrations":
                session_id = parts[3]
                return _send_json(self, mock_calibrations.get(session_id, []))

        return _send_json(self, {})

    def do_POST(self):
        """Handle POST requests"""
        path = urlparse(self.path).path

        if path == "/api/sessions":
            try:
                data = _read_json(self)
                session_id = str(uuid.uuid4())
                now = _iso_now()
                session = {
                    "id": session_id,
                    "player_id": data.get("player_id") if isinstance(data, dict) else None,
                    "started_at": now,
                    "created_at": now,
                }
                mock_sessions[session_id] = session
                mock_shots[session_id] = []
                mock_calibrations[session_id] = []
                print(f"[ok] Created session: {session_id}")
                return _send_json(self, session)
            except Exception as e:
                print(f"[error] Error creating session: {e}")
                return _send_json(self, {"error": str(e)}, status=500)

        if path.startswith("/api/sessions/") and path.endswith("/calibrations"):
            # POST /api/sessions/{id}/calibrations
            parts = path.split("/")
            if len(parts) != 5:
                return _send_json(self, {}, status=404)
            session_id = parts[3]
            if session_id not in mock_sessions:
                return _send_json(self, {"error": "session not found"}, status=404)

            try:
                data = _read_json(self)
                rtt_ms = int(data.get("rtt_ms", 0)) if isinstance(data, dict) else 0
                offset_ms = int(data.get("offset_ms", 0)) if isinstance(data, dict) else 0
                calibration = {
                    "id": str(uuid.uuid4()),
                    "session_id": session_id,
                    "calibrated_at": _iso_now(),
                    "rtt_ms": rtt_ms,
                    "offset_ms": offset_ms,
                    "quality": "mock",
                }
                mock_calibrations.setdefault(session_id, []).append(calibration)
                return _send_json(self, calibration)
            except Exception as e:
                return _send_json(self, {"error": str(e)}, status=500)

        if path.startswith("/api/sessions/") and path.endswith("/shots"):
            # POST /api/sessions/{id}/shots
            parts = path.split("/")
            if len(parts) != 5:
                return _send_json(self, {}, status=404)
            session_id = parts[3]
            if session_id not in mock_sessions:
                return _send_json(self, {"error": "session not found"}, status=404)

            try:
                overrides = _read_json(self)
                shot = _generate_shot(session_id, overrides if isinstance(overrides, dict) else None)
                mock_shots.setdefault(session_id, []).append(shot)
                # Keep session shot_count up to date for UI.
                mock_sessions[session_id]["shot_count"] = len(mock_shots[session_id])
                return _send_json(self, shot)
            except Exception as e:
                return _send_json(self, {"error": str(e)}, status=500)

        return _send_json(self, {})

    def do_PATCH(self):
        """Handle PATCH requests"""
        path = urlparse(self.path).path
        if path.startswith("/api/sessions/"):
            parts = path.split("/")
            if len(parts) != 4:
                return _send_json(self, {}, status=404)
            session_id = parts[3]
            session = mock_sessions.get(session_id)
            if not session:
                return _send_json(self, {"error": "session not found"}, status=404)

            try:
                updates = _read_json(self)
                if isinstance(updates, dict):
                    # Only allow known fields from the frontend.
                    for key in ("ended_at", "video_file_path", "fps", "sync_quality", "shot_count"):
                        if key in updates:
                            session[key] = updates[key]
                mock_sessions[session_id] = session
                return _send_json(self, session)
            except Exception as e:
                return _send_json(self, {"error": str(e)}, status=500)

        return _send_json(self, {}, status=404)

    def log_message(self, format, *args):
        """Suppress default logging"""
        pass

def start_http_server():
    """Start HTTP API server"""
    server = ReusableHTTPServer(("127.0.0.1", 8000), APIHandler)
    print("Mock API Server running on http://127.0.0.1:8000")
    print("POST /api/sessions - Create session")
    print("GET /api/sessions - List sessions")
    print("GET /api/sessions/{id} - Get session")
    print("GET /api/sessions/{id}/shots - List shots")
    print("GET /api/sessions/{id}/shots/stats - Shot stats")
    print("POST /api/sessions/{id}/calibrations - Record clock sync")
    print("PATCH /api/sessions/{id} - Update session")
    print()
    
    server_thread = Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    
    return server

if __name__ == '__main__':
    print("=" * 50)
    print("ONYX MOCK BACKEND - Local Testing Server")
    print("=" * 50)
    print()
    
    server = start_http_server()
    
    try:
        print("Server running. Press Ctrl+C to stop.")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nServer stopped")
        server.shutdown()

