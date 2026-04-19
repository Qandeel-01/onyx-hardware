-- =====================================================================
-- Project ONYX — Hybrid Sensor + CV Schema Migration
-- Target: PostgreSQL 14+
-- Adds: wearable devices, clock sync logs, sensor events, video events,
--       fused shots. Assumes existing `users` and `matches` tables.
-- =====================================================================

BEGIN;

-- ---------------------------------------------------------------------
-- Enums
-- ---------------------------------------------------------------------
DO $$ BEGIN
    CREATE TYPE session_status AS ENUM (
        'pending', 'calibrating', 'active', 'ended', 'processing', 'ready', 'failed'
    );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE shot_type AS ENUM (
        'forehand', 'backhand', 'smash', 'volley_fh', 'volley_bh',
        'bandeja', 'vibora', 'serve', 'lob', 'unknown'
    );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE video_encoding_status AS ENUM (
        'recording', 'uploaded', 'probing', 'ready', 'failed'
    );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- ---------------------------------------------------------------------
-- Sessions (the master container for a recording period)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sessions (
    id                       BIGSERIAL PRIMARY KEY,
    user_id                  BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    match_id                 BIGINT REFERENCES matches(id) ON DELETE SET NULL,
    status                   session_status NOT NULL DEFAULT 'pending',

    started_at_utc           TIMESTAMPTZ,
    ended_at_utc             TIMESTAMPTZ,

    -- Calibration state (populated during calibration flow)
    calibration_complete     BOOLEAN NOT NULL DEFAULT FALSE,
    residual_offset_ms       INTEGER,                       -- from LED flash, in ms
    residual_offset_stddev_ms REAL,                         -- quality of the flash fit
    court_homography         JSONB,                         -- 3x3 matrix
    court_corners_px         JSONB,                         -- {"tl":[x,y], "tr":..., "br":..., "bl":...}

    -- Free-form notes, tags
    metadata                 JSONB NOT NULL DEFAULT '{}'::jsonb,

    created_at               TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at               TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sessions_user_started
    ON sessions (user_id, started_at_utc DESC);
CREATE INDEX IF NOT EXISTS idx_sessions_status
    ON sessions (status) WHERE status IN ('active', 'processing');

-- ---------------------------------------------------------------------
-- Wearable devices (hardware registry)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS wearable_devices (
    id                 BIGSERIAL PRIMARY KEY,
    user_id            BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    mac_address        TEXT NOT NULL UNIQUE,
    device_name        TEXT,
    firmware_version   TEXT,
    hardware_revision  TEXT,                                -- "BNO055-v2", "MPU6050-v1"
    last_seen_at       TIMESTAMPTZ,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_wearables_user
    ON wearable_devices (user_id);

-- ---------------------------------------------------------------------
-- Clock sync log — every SNTP exchange is stored for drift reconstruction
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS session_clock_syncs (
    id                 BIGSERIAL PRIMARY KEY,
    session_id         BIGINT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    device_id          BIGINT NOT NULL REFERENCES wearable_devices(id) ON DELETE CASCADE,

    -- Raw exchange timestamps
    t1_device_ms       BIGINT NOT NULL,                     -- client send (device millis)
    t2_server_utc_ms   BIGINT NOT NULL,                     -- server recv (UTC ms)
    t3_server_utc_ms   BIGINT NOT NULL,                     -- server send (UTC ms)
    t4_device_ms       BIGINT NOT NULL,                     -- client recv (device millis)

    -- Derived metrics
    rtt_ms             REAL NOT NULL,
    offset_ms          DOUBLE PRECISION NOT NULL,           -- device→server offset
    is_selected        BOOLEAN NOT NULL DEFAULT FALSE,      -- min-RTT winner of its batch

    sync_at_utc        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    batch_id           UUID NOT NULL                        -- groups the N samples of one sync cycle
);

CREATE INDEX IF NOT EXISTS idx_clock_syncs_session_device_time
    ON session_clock_syncs (session_id, device_id, t1_device_ms);
CREATE INDEX IF NOT EXISTS idx_clock_syncs_selected
    ON session_clock_syncs (session_id, device_id, sync_at_utc)
    WHERE is_selected = TRUE;

-- ---------------------------------------------------------------------
-- Session videos — one session may have multiple camera angles
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS session_videos (
    id                          BIGSERIAL PRIMARY KEY,
    session_id                  BIGINT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    is_primary                  BOOLEAN NOT NULL DEFAULT FALSE,

    file_uri                    TEXT NOT NULL,              -- s3://... or file:///...
    codec                       TEXT,
    container                   TEXT,                       -- mp4, mkv, webm
    fps                         REAL NOT NULL,
    width_px                    INTEGER NOT NULL,
    height_px                   INTEGER NOT NULL,
    duration_ms                 INTEGER,
    frame_count                 INTEGER,

    -- The critical anchor for fusion
    recording_started_at_utc    TIMESTAMPTZ NOT NULL,
    recording_started_at_utc_ms BIGINT NOT NULL,            -- denormalized for fast math

    -- For VFR sources. NULL implies CFR: compute frame times from fps.
    frame_pts_ms                BIGINT[],

    encoding_status             video_encoding_status NOT NULL DEFAULT 'recording',
    probe_metadata              JSONB,                      -- ffprobe output

    created_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Only one primary video per session
    EXCLUDE (session_id WITH =) WHERE (is_primary = TRUE)
);

CREATE INDEX IF NOT EXISTS idx_videos_session
    ON session_videos (session_id);

-- ---------------------------------------------------------------------
-- Sensor events — raw IMU-detected shots, APPEND-ONLY
-- This is the ground truth stream from the wearable. Never rewrite.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sensor_events (
    id                    BIGSERIAL PRIMARY KEY,
    session_id            BIGINT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    device_id             BIGINT NOT NULL REFERENCES wearable_devices(id) ON DELETE CASCADE,

    -- Device-native timestamp (millis() at event)
    device_ts_ms          BIGINT NOT NULL,
    -- Server ingest time (useful for latency analysis)
    ingested_at_utc       TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    shot_type             shot_type NOT NULL,
    confidence            REAL NOT NULL CHECK (confidence BETWEEN 0 AND 1),

    -- Raw features for retraining and debugging
    -- { peak_accel_mps2, peak_gyro_radps, swing_duration_ms, orientation_quat, ... }
    raw_features          JSONB NOT NULL DEFAULT '{}'::jsonb,

    -- Populated only if the device itself sends a derived UTC guess;
    -- authoritative fusion always recomputes from clock_syncs + residual_offset.
    reported_utc_ms       BIGINT
);

-- BRIN index is 1000x smaller than BTREE for monotonic time columns
CREATE INDEX IF NOT EXISTS idx_sensor_events_session_time_brin
    ON sensor_events USING BRIN (session_id, device_ts_ms);
CREATE INDEX IF NOT EXISTS idx_sensor_events_session_device_time
    ON sensor_events (session_id, device_id, device_ts_ms);
CREATE INDEX IF NOT EXISTS idx_sensor_events_shot_type
    ON sensor_events (session_id, shot_type);

-- ---------------------------------------------------------------------
-- Video frame events — per-frame CV observations
-- Populated by the YOLO+pose worker. One row per detected frame of interest.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS video_frame_events (
    id                    BIGSERIAL PRIMARY KEY,
    session_video_id      BIGINT NOT NULL REFERENCES session_videos(id) ON DELETE CASCADE,
    frame_index           INTEGER NOT NULL,
    frame_ts_ms           BIGINT NOT NULL,                  -- UTC ms (precomputed)

    player_id             INTEGER,                          -- 1..4 in doubles
    court_x_m             REAL,                             -- meters, from homography
    court_y_m             REAL,
    bbox_xywh             INTEGER[],                        -- raw YOLO bbox in pixels

    pose_keypoints        JSONB,                            -- {"nose":[x,y,c], ...}
    pose_quality          REAL,

    ball_detected         BOOLEAN NOT NULL DEFAULT FALSE,
    ball_court_x_m        REAL,
    ball_court_y_m        REAL,
    ball_confidence       REAL,

    extra                 JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_vfe_video_frame
    ON video_frame_events (session_video_id, frame_index);
CREATE INDEX IF NOT EXISTS idx_vfe_video_time_brin
    ON video_frame_events USING BRIN (session_video_id, frame_ts_ms);

-- ---------------------------------------------------------------------
-- Fused shots — the analytical table. Deterministic rebuild from
-- sensor_events ⨝ video_frame_events. Drop & rebuild when fusion changes.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS fused_shots (
    id                    BIGSERIAL PRIMARY KEY,
    session_id            BIGINT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,

    -- Either may be NULL during live-mode before CV finishes
    sensor_event_id       BIGINT REFERENCES sensor_events(id) ON DELETE SET NULL,
    session_video_id      BIGINT REFERENCES session_videos(id) ON DELETE SET NULL,

    -- Frame range around impact
    frame_index_start     INTEGER,
    frame_index_peak      INTEGER,
    frame_index_end       INTEGER,

    -- Timeline (the single-axis UTC ms anchor)
    shot_utc_ms           BIGINT NOT NULL,

    -- What (from IMU)
    shot_type             shot_type NOT NULL,
    shot_subtype          TEXT,                             -- "topspin", "slice", "flat"
    imu_confidence        REAL,

    -- Where (from CV)
    player_id             INTEGER,
    court_x_m             REAL,
    court_y_m             REAL,

    -- How (derived)
    ball_speed_mps        REAL,
    swing_speed_mps       REAL,
    pose_quality          REAL,

    -- Fusion diagnostics
    fusion_confidence     REAL NOT NULL DEFAULT 0,          -- combined score
    fusion_flags          TEXT[],                           -- ['imu_only','cv_only','time_mismatch']

    created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_fused_session_time
    ON fused_shots (session_id, shot_utc_ms);
CREATE INDEX IF NOT EXISTS idx_fused_session_type
    ON fused_shots (session_id, shot_type);
CREATE UNIQUE INDEX IF NOT EXISTS uq_fused_sensor_event
    ON fused_shots (sensor_event_id) WHERE sensor_event_id IS NOT NULL;

-- ---------------------------------------------------------------------
-- Convenience view: a session-at-a-glance
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW v_session_overview AS
SELECT
    s.id                              AS session_id,
    s.user_id,
    s.status,
    s.started_at_utc,
    s.ended_at_utc,
    EXTRACT(EPOCH FROM (s.ended_at_utc - s.started_at_utc)) AS duration_s,
    s.calibration_complete,
    s.residual_offset_ms,
    (SELECT COUNT(*) FROM sensor_events   se WHERE se.session_id = s.id) AS sensor_event_count,
    (SELECT COUNT(*) FROM fused_shots     fs WHERE fs.session_id = s.id) AS fused_shot_count,
    (SELECT COUNT(*) FROM session_videos  sv WHERE sv.session_id = s.id) AS video_count
FROM sessions s;

-- ---------------------------------------------------------------------
-- Trigger: updated_at on sessions
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION touch_updated_at() RETURNS trigger AS $$
BEGIN
    NEW.updated_at := NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_sessions_updated_at ON sessions;
CREATE TRIGGER trg_sessions_updated_at
    BEFORE UPDATE ON sessions
    FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

COMMIT;

-- =====================================================================
-- Sanity-check queries (run these after migration)
-- =====================================================================
-- \d+ sessions
-- \d+ sensor_events
-- SELECT indexname, indexdef FROM pg_indexes
--   WHERE tablename IN ('sensor_events','video_frame_events','session_clock_syncs')
--   ORDER BY tablename, indexname;
