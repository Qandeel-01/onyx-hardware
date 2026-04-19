# Project ONYX — Hybrid Sensor + CV Analysis Architecture

Design document for transitioning from video-only analysis to a fused IMU + CV pipeline. Covers clock synchronization, data flow, database schema, React dashboard structure, and calibration procedure.

---

## 0. The Core Problem

Three independent clocks must be reconciled into one timeline:

| Clock | Source | Characteristics |
|---|---|---|
| **A** — Device | ESP32 `millis()` | High resolution (~1ms), arbitrary epoch (0 at boot), ±20–50 ppm crystal drift |
| **B** — Camera host | Browser `performance.now()` / OS monotonic | Independent epoch, separate drift |
| **C** — Server | FastAPI `time.time_ns()` UTC | **Authoritative master clock** |

Every event — IMU shot detection, video frame capture, user action — must be expressed on Clock C before fusion. Fusion then becomes trivial:

```
shot_utc_ms = device_ts_ms + offset_A→C
frame_index = round((shot_utc_ms − video_start_utc_ms) × fps / 1000)
```

The engineering work is estimating `offset_A→C` and `video_start_utc_ms` accurately and keeping them accurate despite drift.

---

## 1. Clock Synchronization Architecture

### 1.1 Wearable → Server offset (SNTP-style four-timestamp exchange)

On WebSocket connect, and every 30 seconds thereafter, the ESP32 initiates a sync exchange:

```
          Device (Clock A)                    Server (Clock C)
              │                                    │
   T1 = millis()                                   │
              │──────── sync_request(T1) ─────────▶│
              │                              T2 = time_ms_utc()
              │                              T3 = time_ms_utc()
              │◀─── sync_response(T1,T2,T3) ───────│
   T4 = millis()                                   │
              │                                    │
```

**Math:**
```
rtt     = (T4 − T1) − (T3 − T2)              # round-trip time
offset  = ((T2 − T1) + (T3 − T4)) / 2        # A→C offset in ms
```

**Jitter reduction:** Collect N=10 samples per sync cycle, keep the sample with minimum RTT (the one least contaminated by scheduling jitter and network queuing). This is the standard NTP "best sample" heuristic.

**Drift compensation:** Store every sync result. Between syncs, interpolate linearly:
```
offset(t) = offset_k + ((t − t_k) / (t_{k+1} − t_k)) × (offset_{k+1} − offset_k)
```
For post-session reprocessing, this corrects for crystal drift — which can drift ~0.18 s/hour on a ±50 ppm part. Not negligible in a 60-minute match.

### 1.2 Video host → Server offset

**Browser-side recording (MediaRecorder):**
- At `recorder.start()`, the frontend immediately calls `POST /sessions/{id}/video/start` with `client_ts_ms = Date.now()`.
- Server responds with its own `server_ts_ms` and the RTT.
- `video_start_utc_ms = server_ts_ms − rtt/2` (assuming symmetric latency).

**External/RTSP camera:**
- Use NTP on the camera host (`chrony` / `w32tm`) to align its monotonic clock with server UTC.
- On recording start, stamp the first frame's PTS against UTC and store in `session_videos.recording_started_at_utc`.

**VFR vs CFR:**
- For constant frame rate (CFR) streams: `frame_ts_ms = video_start_utc_ms + frame_index × (1000 / fps)`.
- For variable frame rate (VFR) streams: extract PTS array via `ffprobe -show_frames -select_streams v -of json` and store as `frame_pts_ms[]` in `session_videos.frame_pts`. Use binary search at fusion time.

### 1.3 The LED flash / "digital clapperboard" — the ground-truth reset

Software sync can be fooled by asymmetric latency, detection lookahead in the IMU pipeline, and encoder buffering. One hardware event visible to both clocks collapses all of that into a single measurable offset.

**Procedure** (see §4.2 for full flow):
1. User presses calibration button on wearable.
2. ESP32 records `T_flash_device` and pulses a high-brightness LED (≥100 ms, bright enough to saturate camera sensor in one frame).
3. ESP32 transmits `{type: "calibration_flash", device_ts_ms: T_flash_device}`.
4. CV pipeline runs a cheap brightness-delta detector on the video, locates frame `F_flash`.
5. Server computes the **residual offset**:
   ```
   measured_utc_at_flash  = T_flash_device + offset_A→C  (software estimate)
   actual_utc_at_flash    = video_start_utc_ms + F_flash × 1000 / fps  (ground truth)
   residual_offset_ms     = actual_utc_at_flash − measured_utc_at_flash
   ```
6. Store `residual_offset_ms` on the session. All subsequent shot events use `offset_A→C + residual_offset_ms`.

This absorbs: IMU detection lookahead (the ~100–200 ms peak-detection window), BLE/WS transport latency, encoder pipeline delay, and any systematic bias in the SNTP estimate. Typical residuals after a good flash calibration are <1 frame.

### 1.4 End-to-end event-to-frame mapping

```python
def shot_to_frame(shot_event, session):
    # 1. Find bracketing sync samples
    syncs = [s for s in session.clock_syncs if s.device_id == shot_event.device_id]
    t_dev = shot_event.device_ts_ms

    # 2. Interpolate offset at event time
    before = max((s for s in syncs if s.device_ts_ms <= t_dev), default=syncs[0])
    after  = min((s for s in syncs if s.device_ts_ms >  t_dev), default=syncs[-1])
    if before is after:
        offset = before.offset_ms
    else:
        frac = (t_dev - before.device_ts_ms) / (after.device_ts_ms - before.device_ts_ms)
        offset = before.offset_ms + frac * (after.offset_ms - before.offset_ms)

    # 3. Apply software offset + hardware residual
    shot_utc_ms = t_dev + offset + session.residual_offset_ms

    # 4. Map to video timeline
    video = session.primary_video
    delta_ms = shot_utc_ms - video.recording_started_at_utc_ms
    if video.frame_pts:   # VFR
        frame_index = bisect_left(video.frame_pts, delta_ms)
    else:                 # CFR
        frame_index = round(delta_ms * video.fps / 1000)
    return max(0, min(frame_index, video.frame_count - 1))
```

---

## 2. Data Flow Pipeline

```
┌─────────────┐  BLE   ┌─────────────┐  WSS  ┌─────────────┐
│  Wearable   │───────▶│   React     │──────▶│   FastAPI   │
│  ESP32+IMU  │        │  Dashboard  │       │   Gateway   │
└─────────────┘        └─────────────┘       └──────┬──────┘
                              │                     │
                              │ MediaRecorder       │ (async queue)
                              ▼                     ▼
                       ┌─────────────┐       ┌─────────────┐
                       │ Video blob  │       │  Postgres   │
                       │ (uploaded)  │       │  events +   │
                       └──────┬──────┘       │  sync log   │
                              │              └─────────────┘
                              ▼                     ▲
                       ┌─────────────┐              │
                       │  YOLO+Pose  │──────────────┘
                       │   worker    │  (fused_shots writeback)
                       └─────────────┘
```

**Two modes:**
- **Live mode** — dashboard shows IMU shots in real time, video records locally or streams; CV runs after session ends.
- **Post-hoc mode** — IMU log + video uploaded together; fusion runs as a batch job.

Both converge on the same `fused_shots` table. The live dashboard renders IMU-only preliminary data, then upgrades rows in place once CV completes (court coords, pose, ball position).

---

## 3. Database Schema

See `schema.sql` for the full migration. Key tables:

| Table | Role |
|---|---|
| `sessions` | Match container. Holds `residual_offset_ms`, session-level calibration data. |
| `wearable_devices` | Hardware registry (MAC, firmware version). |
| `session_clock_syncs` | Every sync sample. Source of truth for drift reconstruction. |
| `session_videos` | One session may have multiple angles. Stores `recording_started_at_utc`, `fps`, `frame_pts` (for VFR). |
| `sensor_events` | Raw IMU-detected shots. Immutable, append-only. |
| `video_frame_events` | CV-derived per-frame observations (court position, pose, ball). |
| `fused_shots` | **The payoff table.** Joins `sensor_events` + `video_frame_events` into the analytical record. |

Design rules:
- **IMU events are sacrosanct.** `sensor_events` is append-only; fusion errors never rewrite them.
- **Fusion is deterministic & reprocessable.** `fused_shots` can be rebuilt from `sensor_events` + `video_frame_events` at any time. If the fusion algorithm improves, drop and rebuild.
- **Timestamps are always UTC (`TIMESTAMPTZ`).** Device-time is `BIGINT` in ms. Never mix.
- **BRIN indexes on time columns.** Sensor events arrive in monotonic order; BRIN is ~1000× smaller than BTREE for this workload.

---

## 4. Calibration Flow

### 4.1 Session-start checklist (enforced in UI)

The "Start Session" button is disabled until all four complete:

1. **Wearable connected** — BLE paired, battery >20%, firmware version known.
2. **Clock sync converged** — ≥5 sync samples collected, RTT stddev <10 ms, estimated offset stable within ±5 ms.
3. **Camera ready** — video stream active, resolution/FPS confirmed, ≥5 s of test recording captured to validate encoder.
4. **Court corners calibrated** — four corners clicked on video preview; homography matrix computed and sanity-checked (court aspect ratio 20:10).

### 4.2 The LED flash routine (5 seconds, mandatory)

Shown to user as a guided flow:

```
Step 1:  "Point the camera at the wearable, from about 1 meter away."
Step 2:  "Hold the wearable still in camera view."
Step 3:  [Countdown: 3, 2, 1]
Step 4:  Wearable fires 3 LED pulses at T, T+500ms, T+1000ms
Step 5:  Frontend sends last 3 seconds of video to /calibrate/flash
Step 6:  Server detects 3 brightness peaks in video, matches to 3 device timestamps
Step 7:  Residual offset = median of 3 deltas (robust to one bad frame)
Step 8:  UI shows "Calibrated: ±4 ms" — session can now start
```

**Why three pulses, not one?** Redundancy against false positives (reflections, someone walking past), and median is robust to a single mis-detection. Pulses at asymmetric intervals (e.g., 500 ms, 1000 ms) rule out periodic noise aliasing.

**Brightness detector** (run server-side, ~5 ms per frame):
```python
def detect_flashes(frames_gray):
    # Frames are grayscale, downsampled to 160×90 for speed
    mean_brightness = frames_gray.mean(axis=(1,2))
    delta = np.diff(mean_brightness)
    peaks = scipy.signal.find_peaks(delta, prominence=15, distance=5)[0]
    return peaks  # frame indices of flash onsets
```

### 4.3 Re-calibration triggers

Force a re-flash if any of these occur mid-session:
- Camera is physically moved (detected via homography drift on court-line features).
- Wearable disconnects and reconnects (device clock may have been restarted).
- Observed fusion confidence drops below threshold for >30 seconds (suggests accumulated drift).

### 4.4 Court (spatial) calibration

Out of scope for this doc since it's already in the existing CV pipeline. Note only that the homography matrix is stored per-session in `sessions.court_homography` (JSONB, 3×3 matrix), and the four clicked court corners are in `sessions.court_corners_px`. Re-calibration is required if the camera pose changes.

---

## 5. React Component Architecture

See `LiveAnalysisDashboard.jsx` and `useSessionWebSocket.js` for the implementation. Layout:

```
<LiveAnalysisPage>                          [page-level route]
│
├── <SessionStatusBar />                    [top: connection, latency, battery]
│
├── <CalibrationPanel />                    [conditional: shown until calibrated]
│
└── <DashboardGrid>                         [2-col layout when active]
    │
    ├── <VideoFeedPanel>                    [left col, 60% width]
    │   ├── <VideoPreview />                [MediaStream or placeholder]
    │   ├── <CourtOverlay />                [SVG: court lines, live ball, player dot]
    │   └── <RecordingControls />
    │
    └── <LiveStatsPanel>                    [right col, 40% width]
        ├── <CurrentShotCard />             [big: last detected shot]
        ├── <ShotCounter />                 [totals by type]
        ├── <ShotDistribution />            [pie/bar chart]
        ├── <RallyTracker />                [current rally length]
        └── <TelemetryGauges />             [latency, drift, sync quality]

    [below grid, full width]
    └── <ShotTimeline />                    [horizontal scrollable timeline]
```

**State management:** A single `SessionContext` provider wraps the page, owning:
- `sessionState` — `{ id, status, startedAt, calibration }`
- `shotStream` — reducer-backed array of shot events
- `deviceState` — `{ connected, battery, latency, syncQuality }`
- `videoState` — `{ recording, startedAtUtcMs, fps, resolution }`

Child components consume via `useSession()` hook. No Redux needed at this scale.

**Hooks provided:**
- `useSessionWebSocket(sessionId)` — manages the WS connection, heartbeat, auto-reconnect, clock sync loop. Returns `{ socket, syncStatus, lastSyncMs, send }`.
- `useShotStream()` — subscribes to shot events, maintains derived stats (counts, rally state).
- `useVideoRecorder()` — wraps MediaRecorder, reports `startedAtUtcMs` on start via server roundtrip.
- `useClockSync(socket)` — runs the SNTP loop, publishes offset to context.

---

## 6. Integration Checklist

Order of operations to stand this up:

1. ☐ Deploy `schema.sql` migration. Verify with `psql` that BRIN indexes exist.
2. ☐ Add `POST /sessions`, `POST /sessions/{id}/video/start`, `WS /sessions/{id}/stream` to FastAPI.
3. ☐ Add `POST /sessions/{id}/calibrate/flash` endpoint running the brightness detector.
4. ☐ Update ESP32 firmware: SNTP exchange on connect, 30 s sync cycle, LED flash on button press.
5. ☐ Wire `LiveAnalysisDashboard` into your React router. Gate on `calibration.complete === true`.
6. ☐ Run a dry session: record 60 s, fire 20 flashes at random, verify residual offset <1 frame.
7. ☐ Write the fusion worker (consumes `sensor_events` + `session_videos`, writes `fused_shots`). Trigger on session end.
8. ☐ Backfill existing video-only sessions by inserting synthetic `sensor_events = NULL` in `fused_shots` — keeps one analytical table.

## 7. Things That Will Bite You Later

- **BLE → WS hop on the phone adds variable latency.** If you can, stream ESP32 → WiFi → backend directly and skip BLE. Otherwise expect ±30 ms jitter on `device_ts_ms` arrival, which the SNTP math handles but detection pipelines don't.
- **MediaRecorder's first chunk is lies.** The `start()` timestamp is buffered; the actual video starts ~100 ms later. Always use the LED flash to pin the true start.
- **IMU peak detection has an inherent look-back window.** If you're using a 200 ms sliding window for shot detection, the `device_ts_ms` you emit is the *window center*, not the impact instant. Decide on a convention and document it. The LED flash residual will absorb the bias but only if it's constant.
- **Postgres `TIMESTAMPTZ` does not store the zone**, just the UTC instant. That's fine — don't let a developer "fix" it later with `TIMESTAMP WITHOUT TIME ZONE`.
- **Don't index `sensor_events.raw_features` JSONB** unless you actually query by features. It's heavy. Store it, query it rarely, index only if a use case emerges.
