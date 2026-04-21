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

// Set VITE_ENABLE_WS=true in `.env` or `.env.local` (Vite only exposes VITE_* at build/dev start).
// Default true when unset so local dev works after a cold start without forgetting the flag.
const WS_ENABLED =
  String(import.meta.env.VITE_ENABLE_WS ?? 'true').toLowerCase() === 'true';

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
  // Same origin as the page so Vite’s `/ws` proxy (see vite.config) reaches FastAPI.
  // REST already defaults to relative `/api` in dev; previously WS used `:8000` here and
  // failed with 1006 when nothing accepted TCP on 8000 from the browser (e.g. API only
  // reachable via the dev proxy, or Docker-only binding).
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
    const ws = wsRef.current;
    wsRef.current = null;
    if (!ws) return;
    // Explicit 1000 avoids browsers surfacing reserved code 1005 ("no status") on unmount/Strict Mode.
    if (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING) {
      ws.close(1000, 'Client closed');
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
        // Send first ping immediately, then every 5s for continuous clock sync.
        queueMicrotask(() => sendSyncPing());
        const pingInterval = window.setInterval(() => {
          if (wsRef.current?.readyState === WebSocket.OPEN) sendSyncPing();
          else window.clearInterval(pingInterval);
        }, 5000);
        (wsRef.current as WebSocket & { _pingInterval?: number })._pingInterval = pingInterval;
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
        const ws = wsRef.current as (WebSocket & { _pingInterval?: number }) | null;
        if (ws?._pingInterval) window.clearInterval(ws._pingInterval);
        setState((prev) => ({ ...prev, connected: false }));
        if (!WS_ENABLED) return;
        // 1000/1001 normal; 1005 = "no status" (often client close() without code or proxy quirk — not actionable).
        if (ev.code === 1000 || ev.code === 1001 || ev.code === 1005) return;
        const reason =
          ev.reason?.trim() ||
          (ev.code === 1006
            ? 'connection failed — confirm API on :8000 (/docs), Postgres up, and Vite proxy /ws (ws: true); restart `npm run dev` after env or vite.config.js changes'
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