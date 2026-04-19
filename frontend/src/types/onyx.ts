/**
 * Project ONYX Type Definitions
 * Complete TypeScript interfaces for padel analytics platform
 * 
 * This module provides strict type definitions for all Project ONYX entities,
 * ensuring type safety across the application without relying on `any` types.
 * 
 * @module types/onyx
 */

/**
 * Court corner position with x, y coordinates and semantic label
 * Used for court calibration and pose estimation
 */
export interface CourtCorner {
  /** X coordinate in pixels or normalized space */
  x: number;
  /** Y coordinate in pixels or normalized space */
  y: number;
  /** Semantic label for court corner location */
  label: 'top_left' | 'top_right' | 'bottom_left' | 'bottom_right';
}

/**
 * Recording session representing a complete padel game/practice
 * Tracks state from creation through archival with calibration metadata
 */
export interface Session {
  /** Unique session identifier */
  id: number;
  /** Associated user identifier */
  user_id: number;
  /** Associated wearable device identifier */
  device_id: number;
  /** Current recording state of the session */
  status: 'created' | 'recording' | 'completed' | 'archived';
  /** Calibration progress state */
  calibration_state: 'not_started' | 'in_progress' | 'completed';
  /** Court corner calibration points */
  court_corners: CourtCorner[];
  /** Latency offset between camera and device clock in milliseconds (null if uncalibrated) */
  flash_residual_offset_ms: number | null;
  /** Session start time in UTC milliseconds (epoch time) */
  session_start_utc_ms: number;
  /** Session end time in UTC milliseconds, null if ongoing */
  session_end_utc_ms: number | null;
  /** ISO 8601 creation timestamp */
  created_at: string;
}

/**
 * Wearable device metadata for athlete tracking
 * Stores device identifiers and firmware information
 */
export interface WearableDevice {
  /** Unique device identifier */
  id: number;
  /** Device owner user identifier */
  user_id: number;
  /** Bluetooth MAC address of the device */
  mac_address: string;
  /** Current firmware version or null if unknown */
  firmware_version: string | null;
  /** ISO 8601 timestamp of last device communication */
  last_seen: string;
}

/**
 * Real-time device status and health metrics
 * Streamed via WebSocket during active sessions
 */
export interface DeviceStatus {
  /** True if device maintains active connection */
  connected: boolean;
  /** Battery percentage (0-100) */
  battery_percent: number;
  /** Last heartbeat timestamp in UTC milliseconds */
  last_heartbeat_utc_ms: number;
  /** Radio signal strength indicator (-100 to 0 dBm) */
  signal_strength: number;
}

/**
 * Single clock synchronization sample from SNTP protocol
 * Four-message handshake for NTP-based clock offset calculation
 * 
 * @see https://en.wikipedia.org/wiki/Network_Time_Protocol
 */
export interface ClockSyncSample {
  /** Device timestamp of T1 (request sent) in milliseconds */
  t1_device_ms: number;
  /** Server timestamp of T2 (request received) in UTC milliseconds */
  t2_server_utc_ms: number;
  /** Server timestamp of T3 (response sent) in UTC milliseconds */
  t3_server_utc_ms: number;
  /** Device timestamp of T4 (response received) in milliseconds */
  t4_device_ms: number;
}

/**
 * Cumulative clock synchronization state and quality metrics
 * Tracks multi-sample NTP sync for camera-device latency correction
 */
export interface ClockSyncState {
  /** Collection of historical sync samples */
  samples: ClockSyncSample[];
  /** Calculated time offset from device to server in milliseconds (null if not synced) */
  offset_ms: number | null;
  /** Subjective quality assessment based on sample variance */
  quality: 'excellent' | 'good' | 'fair' | 'poor' | 'unknown';
  /** True if active synchronization is in progress */
  is_syncing: boolean;
}

/**
 * Raw accelerometer event detected by device sensor
 * Represents a single motion event potentially indicating a paddle strike
 */
export interface SensorEvent {
  /** Unique event identifier */
  id: number;
  /** Device-local timestamp in milliseconds */
  device_ts_ms: number;
  /** Predicted shot type from ML model */
  shot_type: string;
  /** ML model confidence score (0-1) */
  confidence: number;
  /** X-axis acceleration in m/s² */
  accel_x: number;
  /** Y-axis acceleration in m/s² */
  accel_y: number;
  /** Z-axis acceleration in m/s² */
  accel_z: number;
}

/**
 * Fused shot with integrated sensor and vision data
 * Final output after multi-modal fusion of accelerometer + video analysis
 */
export interface FusedShot {
  /** Unique shot identifier */
  id: number;
  /** Classified shot type (forehand, backhand, volley, etc.) */
  shot_type: string;
  /** X coordinate on court in meters */
  court_x_m: number;
  /** Y coordinate on court in meters */
  court_y_m: number;
  /** Sensor model confidence (0-1) */
  sensor_confidence: number;
  /** Vision model confidence (0-1), null if no vision data available */
  vision_confidence: number | null;
  /** Final fused confidence score combining both modalities (0-1) */
  fusion_confidence: number;
  /** ISO 8601 creation timestamp */
  created_at: string;
}

/**
 * Video file metadata for session recordings
 * Tracks encoding status and video stream characteristics
 */
export interface VideoFile {
  /** Unique video file identifier */
  id: number;
  /** File system path or object storage key */
  file_path: string;
  /** Frames per second of recording */
  fps: number;
  /** Total number of video frames */
  frame_count: number;
  /** Video duration in seconds */
  duration_seconds: number;
  /** Video encoding pipeline status */
  encoding_status: 'pending' | 'processing' | 'complete';
}

/**
 * Single step in multi-step calibration workflow
 * Tracks completion state and errors for each calibration phase
 */
export interface CalibrationStep {
  /** Name of calibration step */
  step: 'corner_picker' | 'flash_setup' | 'flash_record' | 'verify';
  /** True if step has completed successfully */
  completed: boolean;
  /** Error message if step failed, null otherwise */
  error: string | null;
}

/**
 * Complete calibration state for court geometry and camera-device sync
 * Aggregates individual calibration steps with validation results
 */
export interface CalibrationState {
  /** Mapping of step names to their completion status */
  steps: Record<string, CalibrationStep>;
  /** Four court corner calibration points */
  court_corners: CourtCorner[];
  /** Camera-device latency offset in milliseconds, null if uncalibrated */
  flash_residual_offset_ms: number | null;
  /** Human-readable calibration quality assessment */
  quality: string;
}

/**
 * SNTP clock synchronization message from device
 * Contains four-message NTP handshake timestamps
 */
export interface SNTPMessage {
  /** Message type discriminator */
  type: 'sntp';
  /** Device T1 timestamp (request sent) in milliseconds */
  t1_ms: number;
  /** Server T2 timestamp (request received) in UTC milliseconds */
  t2_ms: number;
  /** Server T3 timestamp (response sent) in UTC milliseconds */
  t3_ms: number;
  /** Device T4 timestamp (response received) in milliseconds */
  t4_ms: number;
}

/**
 * Shot detection event from wearable sensor
 * Real-time notification of detected paddle strike
 */
export interface ShotMessage {
  /** Message type discriminator */
  type: 'shot';
  /** Sensor event data */
  data: SensorEvent;
}

/**
 * Device health and connectivity status update
 * Periodic status notification from device
 */
export interface StatusMessage {
  /** Message type discriminator */
  type: 'status';
  /** Current device status metrics */
  data: DeviceStatus;
}

/**
 * Flash calibration completion notification
 * Sent when latency offset has been calculated
 */
export interface CalibratedMessage {
  /** Message type discriminator */
  type: 'calibrated';
  /** Calculated residual latency in milliseconds */
  residual_offset_ms: number;
}

/**
 * Union type for all WebSocket message variants
 * Type guard enables discriminated union pattern
 */
export type WebSocketMessage = 
  | SNTPMessage 
  | ShotMessage 
  | StatusMessage 
  | CalibratedMessage;

/**
 * Type guard to narrow WebSocketMessage to specific type
 * @param message - The message to check
 * @param type - The expected message type
 * @returns True if message matches the specified type
 */
export function isWebSocketMessageType<T extends WebSocketMessage['type']>(
  message: WebSocketMessage,
  type: T
): message is Extract<WebSocketMessage, { type: T }> {
  return message.type === type;
}
