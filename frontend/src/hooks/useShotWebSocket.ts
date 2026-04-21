/**
 * Custom React hook for real-time shot streaming via WebSocket
 * Implements clock synchronization protocol: SYNC_PING/PONG + shot events
 */
import { useEffect, useRef, useState, useCallback } from 'react';
import { ShotEvent, WebSocketMessage, ShotType } from '@/types';

interface UseShotWebSocketOptions {
  sessionId: string;
  onShotReceived?: (shot: ShotEvent) => void;
  onError?: (error: string) => void;
  onCalibrated?: (offsetMs: number, rttMs: number) => void;
}

interface WebSocketState {
  connected: boolean;
  calibrated: boolean;
  offsetMs: number;
  rttMs: number;
}

const WS_ENABLED =
  String(import.meta.env.VITE_ENABLE_WS ?? 'false').toLowerCase() === 'true';

/** Host part for URLs (IPv6 needs brackets). */
function wsHostFromLocation(): string {
  const h = window.location.hostname;
  if (h.includes(':') && !h.startsWith('[')) {
    return `[${h}]`;
  }
  return h;
}

/** Backend origin for WebSocket (must match where FastAPI runs). */
function getWebSocketBaseUrl(): string {
  const explicit = import.meta.env.VITE_WS_URL as string | undefined;
  if (explicit?.trim()) {
    return explicit.trim().replace(/\/$/, '');
  }
  const apiHttp = import.meta.env.VITE_API_URL || import.meta.env.VITE_API_BASE_URL;
  if (typeof apiHttp === 'string' && /^https?:\/\//i.test(apiHttp)) {
    try {
      const u = new URL(apiHttp.replace(/\/$/, ''));
      const wsScheme = u.protocol === 'https:' ? 'wss:' : 'ws:';
      return `${wsScheme}//${u.host}`;
    } catch {
      /* fall through */
    }
  }
  // Dev: connect to API on same host as the page (not 127.0.0.1 — that breaks when you open
  // http://192.168.x.x:5173 or from another device; 127.0.0.1 would target the client only).
  if (import.meta.env.DEV) {
    const wsScheme = window.location.protocol === 'https:' ? 'wss' : 'ws';
    return `${wsScheme}://${wsHostFromLocation()}:8000`;
  }
  const wsScheme = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${wsScheme}//${window.location.host}`;
}

export const useShotWebSocket = ({
  sessionId,
  onShotReceived,
  onError,
  onCalibrated,
}: UseShotWebSocketOptions) => {
  const wsRef = useRef<WebSocket | null>(null);
  const [state, setState] = useState<WebSocketState>({
    connected: false,
    calibrated: false,
    offsetMs: 0,
    rttMs: 0,
  });
  const pingStartRef = useRef<number>(0);

  const onShotReceivedRef = useRef(onShotReceived);
  const onErrorRef = useRef(onError);
  const onCalibratedRef = useRef(onCalibrated);
  onShotReceivedRef.current = onShotReceived;
  onErrorRef.current = onError;
  onCalibratedRef.current = onCalibrated;

  const sendSyncPing = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      pingStartRef.current = Date.now();
      const message = {
        type: 'SYNC_PING',
        browser_ts: Date.now(),
      };
      wsRef.current.send(JSON.stringify(message));
    }
  }, []);

  const handleMessage = useCallback((raw: string) => {
    try {
      const message = JSON.parse(raw) as WebSocketMessage;
      switch (message.type) {
        case 'SYNC_PONG': {
          const rttMs = Date.now() - pingStartRef.current;
          const deviceTs = message.device_ts as number | undefined;
          const echoBrowser = message.echo_browser_ts as number | undefined;
          let offsetMs: number;
          if (typeof message.offset_ms === 'number') {
            offsetMs = message.offset_ms;
          } else if (deviceTs != null && echoBrowser != null) {
            offsetMs = deviceTs - echoBrowser - rttMs / 2;
          } else {
            offsetMs = 0;
          }
          setState((prev) => ({
            ...prev,
            calibrated: true,
            offsetMs,
            rttMs,
          }));
          onCalibratedRef.current?.(offsetMs, rttMs);
          break;
        }
        case 'SHOT_EVENT': {
          const deviceTsMs = message.device_ts_ms as number;
          const shot: ShotEvent = {
            id: message.id as string,
            session_id: (message.session_id as string) ?? sessionId,
            shot_type: message.shot_type as ShotType,
            confidence: message.confidence as number,
            device_ts: deviceTsMs,
            wall_clock_ts:
              typeof message.timestamp === 'string'
                ? message.timestamp
                : new Date().toISOString(),
            accel_x: message.accel_x as number | undefined,
            accel_y: message.accel_y as number | undefined,
            accel_z: message.accel_z as number | undefined,
            gyro_x: message.gyro_x as number | undefined,
            gyro_y: message.gyro_y as number | undefined,
            gyro_z: message.gyro_z as number | undefined,
            created_at: new Date().toISOString(),
          };
          onShotReceivedRef.current?.(shot);
          break;
        }
        default:
          break;
      }
    } catch (err) {
      onErrorRef.current?.(`Failed to parse message: ${err}`);
    }
  }, [sessionId]);

  const handleMessageRef = useRef(handleMessage);
  handleMessageRef.current = handleMessage;

  const disconnect = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
  }, []);

  const connect = useCallback(() => {
    if (!WS_ENABLED) {
      return;
    }
    try {
      const base = getWebSocketBaseUrl();
      const wsUrl = `${base}/ws/shots/${sessionId}`;

      wsRef.current = new WebSocket(wsUrl);

      wsRef.current.onopen = () => {
        setState((prev) => ({ ...prev, connected: true }));
        queueMicrotask(() => sendSyncPing());
      };

      wsRef.current.onmessage = (event) => {
        handleMessageRef.current(event.data as string);
      };

      wsRef.current.onerror = () => {
        setState((prev) => ({ ...prev, connected: false }));
        onErrorRef.current?.(
          `WebSocket error (${wsUrl}). Run: uvicorn with --host 0.0.0.0 --port 8000; open DB; valid session id.`
        );
      };

      wsRef.current.onclose = (ev) => {
        setState((prev) => ({ ...prev, connected: false }));
        if (!WS_ENABLED) return;
        if (ev.code === 1000 || ev.code === 1001) return;
        const reason =
          ev.reason?.trim() ||
          (ev.code === 1006
            ? 'connection failed — start API on port 8000 (uvicorn --host 0.0.0.0), PostgreSQL up, session from POST /api/sessions'
            : `closed with code ${ev.code}`);
        onErrorRef.current?.(`WebSocket: ${reason}`);
      };
    } catch (err) {
      onErrorRef.current?.(`Failed to connect: ${err}`);
    }
  }, [sessionId, sendSyncPing]);

  useEffect(() => {
    connect();
    return () => {
      disconnect();
    };
  }, [connect, disconnect]);

  return {
    connected: WS_ENABLED ? state.connected : false,
    calibrated: state.calibrated,
    offsetMs: state.offsetMs,
    rttMs: state.rttMs,
    sendSyncPing: WS_ENABLED ? sendSyncPing : () => {},
    wsEnabled: WS_ENABLED,
  };
};
