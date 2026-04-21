/**
 * Type definitions for Project ONYX frontend
 */

export enum ShotType {
  FOREHAND = "Forehand",
  BACKHAND = "Backhand",
  SMASH = "Smash",
  VOLLEY = "Volley",
  BANDEJA = "Bandeja",
  LOB = "Lob",
}

export interface ShotEvent {
  id: string;
  session_id: string;
  shot_type: ShotType;
  confidence: number;
  device_ts: number;
  wall_clock_ts?: string;
  frame_index?: number;
  court_x?: number;
  court_y?: number;
  player_bbox?: Record<string, unknown>;
  pose_keypoints?: unknown[];
  accel_x?: number;
  accel_y?: number;
  accel_z?: number;
  gyro_x?: number;
  gyro_y?: number;
  gyro_z?: number;
  created_at: string;
}

export interface Session {
  id: string;
  player_id?: string;
  started_at: string;
  ended_at?: string;
  video_file_path?: string;
  fps?: number;
  sync_quality?: string;
  shot_count?: number;
  created_at: string;
}

export interface ClockCalibration {
  id: string;
  session_id: string;
  calibrated_at: string;
  rtt_ms: number;
  offset_ms: number;
  quality: string;
}

export interface WebSocketMessage {
  type: "SYNC_PING" | "SYNC_PONG" | "SHOT_EVENT";
  /** Server may send ISO time string on SHOT_EVENT */
  timestamp?: number | string;
  offset_ms?: number;
  device_ts?: number;
  echo_browser_ts?: number;
  shot_type?: ShotType;
  confidence?: number;
  device_ts_ms?: number;
  [key: string]: unknown;
}

export interface ShotStats {
  total_shots: number;
  distribution: ShotDistribution[];
  avg_confidence: number;
  earliest_ts: number;
  latest_ts: number;
}

export interface ShotDistribution {
  shot_type: ShotType;
  count: number;
  avg_confidence: number;
  max_confidence: number;
  min_confidence: number;
}
