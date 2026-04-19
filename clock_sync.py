# clock_sync.py
# FastAPI routes and WebSocket handler for Project ONYX synchronization.
# Implements:
#   - SNTP-style clock sync exchange
#   - Video start timestamp handshake
#   - Flash calibration (3-pulse LED detection)
#   - Sensor event ingest
#
# Assumes SQLAlchemy session factory `get_db`, auth dep `get_current_user`,
# and your existing session/device models. Adapt imports as needed.

from __future__ import annotations

import asyncio
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

import numpy as np
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, UploadFile, File
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session as DBSession

# -- adapt these imports to your project structure ---------------------
from .db import get_db
from .auth import get_current_user
from .models import Session, WearableDevice, SessionClockSync, SensorEvent, SessionVideo
# ---------------------------------------------------------------------

router = APIRouter(prefix="/sessions", tags=["sessions"])


def utc_ms() -> int:
    """Authoritative master clock. Nanosecond precision, truncated to ms."""
    return time.time_ns() // 1_000_000


# =====================================================================
# Pydantic schemas
# =====================================================================
class VideoStartRequest(BaseModel):
    client_ts_ms: int = Field(..., description="Date.now() at recorder.start()")


class VideoStartResponse(BaseModel):
    server_ts_ms: int
    rtt_ms: int
    video_id: int


class FlashCalibrationResponse(BaseModel):
    detected_flash_frames: list[int]
    detected_flash_utc_ms: list[int]
    device_flash_utc_ms: list[int]
    residual_offset_ms: float
    residual_offset_stddev_ms: float


# =====================================================================
# Video start handshake
# =====================================================================
@router.post("/{session_id}/video/start", response_model=VideoStartResponse)
async def video_start(
    session_id: int,
    body: VideoStartRequest,
    db: DBSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """
    Frontend calls this the instant MediaRecorder.start() fires.
    We record server UTC as the authoritative video start and
    return it along with estimated RTT for offset correction.
    """
    t_server_recv = utc_ms()
    rtt_ms = max(0, t_server_recv - body.client_ts_ms)
    # Symmetric-latency assumption: true start ≈ server_recv − rtt/2
    video_start_utc = t_server_recv - rtt_ms // 2

    sess = db.query(Session).filter_by(id=session_id, user_id=user.id).first()
    if not sess:
        raise HTTPException(404, "session not found")

    video = SessionVideo(
        session_id=session_id,
        is_primary=True,
        file_uri="pending://browser",  # filled in on upload
        fps=30.0,
        width_px=1280,
        height_px=720,
        recording_started_at_utc=datetime.fromtimestamp(video_start_utc / 1000, tz=timezone.utc),
        recording_started_at_utc_ms=video_start_utc,
        encoding_status="recording",
    )
    db.add(video)
    db.commit()
    db.refresh(video)

    return VideoStartResponse(
        server_ts_ms=t_server_recv,
        rtt_ms=rtt_ms,
        video_id=video.id,
    )


# =====================================================================
# Flash calibration endpoint
# =====================================================================
@router.post("/{session_id}/calibrate/flash", response_model=FlashCalibrationResponse)
async def calibrate_flash(
    session_id: int,
    video_clip: UploadFile = File(...),
    device_flash_timestamps_ms: list[int] = ...,  # sent as form field; parse in prod
    db: DBSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """
    Process a short video clip (~3s) containing 3 LED pulses from the wearable,
    match detected flashes to device-reported pulse timestamps, compute the
    residual offset, and persist it on the session.
    """
    sess = db.query(Session).filter_by(id=session_id, user_id=user.id).first()
    if not sess:
        raise HTTPException(404, "session not found")
    video = db.query(SessionVideo).filter_by(session_id=session_id, is_primary=True).first()
    if not video:
        raise HTTPException(400, "no primary video for session")

    # Run brightness-delta detector
    frame_indices = await _detect_flash_frames(video_clip)
    if len(frame_indices) < len(device_flash_timestamps_ms):
        raise HTTPException(422, f"detected {len(frame_indices)} flashes, expected {len(device_flash_timestamps_ms)}")

    # Convert detected frame indices to UTC
    detected_utc = [
        video.recording_started_at_utc_ms + int(idx * 1000 / video.fps)
        for idx in frame_indices[: len(device_flash_timestamps_ms)]
    ]

    # Translate device-side flash timestamps to server UTC using the
    # currently-stored software offset, then compute the residual delta.
    latest_sync = (
        db.query(SessionClockSync)
        .filter_by(session_id=session_id, is_selected=True)
        .order_by(SessionClockSync.sync_at_utc.desc())
        .first()
    )
    if not latest_sync:
        raise HTTPException(400, "no clock sync data — run sync first")

    device_utc = [int(ts + latest_sync.offset_ms) for ts in device_flash_timestamps_ms]
    deltas = np.array(detected_utc) - np.array(device_utc)

    # Robust estimator: median + MAD-based stddev
    residual = float(np.median(deltas))
    mad = float(np.median(np.abs(deltas - residual)))
    stddev = 1.4826 * mad  # MAD → stddev under Gaussian assumption

    sess.residual_offset_ms = int(round(residual))
    sess.residual_offset_stddev_ms = stddev
    sess.calibration_complete = True
    db.commit()

    return FlashCalibrationResponse(
        detected_flash_frames=frame_indices,
        detected_flash_utc_ms=detected_utc,
        device_flash_utc_ms=device_utc,
        residual_offset_ms=residual,
        residual_offset_stddev_ms=stddev,
    )


async def _detect_flash_frames(upload: UploadFile) -> list[int]:
    """
    Cheap brightness-delta detector. Downsample to 160x90 grayscale, compute
    mean per frame, run peak detection on the first-difference signal.
    Returns sorted frame indices of flash onsets.
    """
    import cv2
    import tempfile
    import scipy.signal as sps

    # Save upload to temp file (OpenCV can't read from async stream directly)
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
        tmp.write(await upload.read())
        tmp_path = tmp.name

    cap = cv2.VideoCapture(tmp_path)
    means = []
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        small = cv2.resize(frame, (160, 90), interpolation=cv2.INTER_AREA)
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        means.append(float(gray.mean()))
    cap.release()

    if len(means) < 3:
        return []

    means = np.asarray(means)
    delta = np.diff(means)
    peaks, _ = sps.find_peaks(delta, prominence=15.0, distance=5)
    return peaks.tolist()


# =====================================================================
# WebSocket handler — streams shot events + handles clock sync
# =====================================================================
@router.websocket("/ws")
async def session_websocket(
    ws: WebSocket,
    session_id: int,
    token: str,
    db: DBSession = Depends(get_db),
):
    """
    Protocol (JSON messages, both directions):

      C→S:  {type: "sync_request", session_id, t1_device_ms}
      S→C:  {type: "sync_response", t1_device_ms, t2_server_utc_ms, t3_server_utc_ms}

      C→S:  {type: "sync_batch_finalized", session_id, selected_t1_device_ms, sample_count}
      C→S:  {type: "shot_event", device_id, device_ts_ms, shot_type, confidence, features}
      C→S:  {type: "device_status", battery, rssi, firmware}
      C→S:  {type: "ping", ts}
      S→C:  {type: "pong", ts}
      S→C:  {type: "shot_event", ...}   (rebroadcast, includes server-assigned id)
      S→C:  {type: "error", message}
    """
    # -- auth ----------------------------------------------------------
    user = await _authenticate_ws(token, db)
    if not user:
        await ws.close(code=1008)
        return
    sess = db.query(Session).filter_by(id=session_id, user_id=user.id).first()
    if not sess:
        await ws.close(code=1008)
        return

    await ws.accept()
    sync_batch: list[SessionClockSync] = []  # buffered until finalize

    try:
        while True:
            msg = await ws.receive_json()
            mtype = msg.get("type")

            # ---- SNTP exchange ---------------------------------------
            if mtype == "sync_request":
                # NB: record t2/t3 bracketing the response construction
                t2 = utc_ms()
                response = {
                    "type": "sync_response",
                    "t1_device_ms": msg["t1_device_ms"],
                    "t2_server_utc_ms": t2,
                    "t3_server_utc_ms": utc_ms(),
                }
                await ws.send_json(response)

                # Buffer this sample — finalize will mark best one
                rec = SessionClockSync(
                    session_id=session_id,
                    device_id=msg.get("device_id", 0),  # resolve from handshake in prod
                    t1_device_ms=msg["t1_device_ms"],
                    t2_server_utc_ms=t2,
                    t3_server_utc_ms=response["t3_server_utc_ms"],
                    t4_device_ms=0,  # client fills later
                    rtt_ms=0.0,
                    offset_ms=0.0,
                    is_selected=False,
                    batch_id=uuid.uuid4(),
                )
                sync_batch.append(rec)

            # ---- Finalize the batch, persist best sample -------------
            elif mtype == "sync_batch_finalized":
                selected_t1 = msg["selected_t1_device_ms"]
                if sync_batch:
                    batch_id = uuid.uuid4()
                    for r in sync_batch:
                        r.batch_id = batch_id
                        r.is_selected = (r.t1_device_ms == selected_t1)
                        # For unselected rows we never learned t4/rtt/offset;
                        # just drop them to keep the table clean:
                        if r.is_selected:
                            db.add(r)
                    db.commit()
                    sync_batch.clear()

            # ---- Shot event ingest -----------------------------------
            elif mtype == "shot_event":
                event = SensorEvent(
                    session_id=session_id,
                    device_id=msg["device_id"],
                    device_ts_ms=msg["device_ts_ms"],
                    shot_type=msg["shot_type"],
                    confidence=msg.get("confidence", 0.5),
                    raw_features=msg.get("features", {}),
                )
                db.add(event)
                db.commit()
                db.refresh(event)

                # Rebroadcast with server-assigned id and ingest timestamp
                await ws.send_json({
                    "type": "shot_event",
                    "id": event.id,
                    "device_id": event.device_id,
                    "device_ts_ms": event.device_ts_ms,
                    "shot_type": event.shot_type,
                    "confidence": event.confidence,
                    "features": event.raw_features,
                    "receivedAt": utc_ms(),
                })

            # ---- Device health ---------------------------------------
            elif mtype == "device_status":
                # Update last_seen and any telemetry
                dev = db.query(WearableDevice).filter_by(id=msg["device_id"]).first()
                if dev:
                    dev.last_seen_at = datetime.now(timezone.utc)
                    if msg.get("firmware"):
                        dev.firmware_version = msg["firmware"]
                    db.commit()

            # ---- Heartbeat -------------------------------------------
            elif mtype == "ping":
                await ws.send_json({"type": "pong", "ts": utc_ms()})

            else:
                await ws.send_json({"type": "error", "message": f"unknown type: {mtype}"})

    except WebSocketDisconnect:
        return
    except Exception as e:
        try:
            await ws.send_json({"type": "error", "message": str(e)})
        finally:
            await ws.close(code=1011)


async def _authenticate_ws(token: str, db: DBSession):
    """Replace with your real auth: JWT verify, session token lookup, etc."""
    # ... your token validation logic ...
    return object()  # placeholder
