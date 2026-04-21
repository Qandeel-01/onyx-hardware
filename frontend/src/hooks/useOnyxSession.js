/**
 * useOnyxSession — relative URLs, all traffic through Vite proxy.
 * Vite forwards /api → http://localhost:8000  and  /ws → ws://localhost:8000
 * so this works in dev (5173) and production (same origin) without changes.
 */
import { useState, useEffect, useRef, useCallback } from 'react';

// No hardcoded ports. Proxy handles the hop.
const API = '/api';
const WS = (path) =>
  `${typeof window !== 'undefined' && window.location.protocol === 'https:' ? 'wss' : 'ws'}://${
    typeof window !== 'undefined' ? window.location.host : ''
  }${path}`;

const BLANK_STATS = {
  total: 0,
  byType: { Forehand: 0, Backhand: 0, Smash: 0, Volley: 0, Bandeja: 0, Lob: 0 },
  avgConfidence: 0,
  confidenceSum: 0,
  rateHistory: [],
  lastShot: null,
};

export function useOnyxSession() {
  const [status, setStatus] = useState('idle');
  const [sessionId, setSessionId] = useState(null);
  const [shots, setShots] = useState([]);
  const [stats, setStats] = useState(BLANK_STATS);
  const [syncOffset, setSyncOffset] = useState(null);
  const [error, setError] = useState(null);

  const wsRef = useRef(null);
  const pingIntervalRef = useRef(null);
  const rateBucketRef = useRef({ t: Date.now(), count: 0 });

  // ── Create session → open WebSocket ──────────────────────────────
  const startSession = useCallback(async (fps = 30) => {
    setStatus('creating');
    setError(null);

    let sid;
    try {
      const res = await fetch(`${API}/sessions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ fps }),
      });
      if (!res.ok) throw new Error(`POST /api/sessions → ${res.status} ${await res.text()}`);
      sid = (await res.json()).id;
      setSessionId(sid);
    } catch (e) {
      setError(e.message);
      setStatus('error');
      return;
    }

    const ws = new WebSocket(WS(`/ws/shots/${sid}`));
    wsRef.current = ws;

    ws.onopen = () => {
      setStatus('connected');
      _ping(ws);
      pingIntervalRef.current = setInterval(() => _ping(ws), 5000);
    };

    ws.onmessage = ({ data }) => {
      let msg;
      try {
        msg = JSON.parse(data);
      } catch {
        return;
      }

      if (msg.type === 'SYNC_PONG') {
        const now = Date.now();
        const rtt = now - (msg.echo_browser_ts ?? now);
        const offset = msg.device_ts - ((msg.echo_browser_ts ?? now) + rtt / 2);
        setSyncOffset({ rtt_ms: rtt, offset_ms: offset });
        return;
      }

      if (msg.type === 'SHOT_EVENT') {
        _ingestShot(msg);
        return;
      }
      if (msg.type === 'ERROR') setError(msg.message);
    };

    ws.onerror = () => {
      setError(
        `WebSocket failed for session ${sid}. ` +
          `Is uvicorn running? Did you restart Vite after editing vite.config?`
      );
      setStatus('error');
    };

    ws.onclose = ({ code }) => {
      clearInterval(pingIntervalRef.current);
      if (code === 4004) setError('Session not found on server (4004).');
      setStatus((s) => (s !== 'idle' ? 'stopped' : s));
    };
  }, []);

  // ── Stop ─────────────────────────────────────────────────────────
  const stopSession = useCallback(async () => {
    clearInterval(pingIntervalRef.current);
    wsRef.current?.close();
    wsRef.current = null;
    setStatus('stopped');
    if (sessionId) {
      await fetch(`${API}/sessions/${sessionId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ended_at: new Date().toISOString() }),
      }).catch(() => {});
    }
  }, [sessionId]);

  // ── Reset ─────────────────────────────────────────────────────────
  const reset = useCallback(() => {
    stopSession();
    setSessionId(null);
    setShots([]);
    setStats(BLANK_STATS);
    setSyncOffset(null);
    setError(null);
    setStatus('idle');
    rateBucketRef.current = { t: Date.now(), count: 0 };
  }, [stopSession]);

  // ── Calibration POST ──────────────────────────────────────────────
  const triggerCalibration = useCallback(async () => {
    if (!sessionId || !syncOffset) return null;
    const res = await fetch(
      `${API}/sessions/${sessionId}/calibrations` +
        `?rtt_ms=${syncOffset.rtt_ms.toFixed(2)}&offset_ms=${syncOffset.offset_ms.toFixed(2)}`,
      { method: 'POST' }
    );
    return res.ok ? res.json() : null;
  }, [sessionId, syncOffset]);

  // ── Internals ─────────────────────────────────────────────────────
  function _ping(ws) {
    if (ws.readyState === WebSocket.OPEN)
      ws.send(JSON.stringify({ type: 'SYNC_PING', browser_ts: Date.now() }));
  }

  function _ingestShot(msg) {
    const shot = {
      id: msg.id,
      type: msg.shot_type,
      confidence: msg.confidence,
      device_ts: msg.device_ts_ms,
      timestamp: msg.timestamp,
      accel: { x: msg.accel_x, y: msg.accel_y, z: msg.accel_z },
      gyro: { x: msg.gyro_x, y: msg.gyro_y, z: msg.gyro_z },
    };

    setShots((prev) => [shot, ...prev].slice(0, 50));

    setStats((prev) => {
      const total = prev.total + 1;
      const byType = { ...prev.byType, [shot.type]: (prev.byType[shot.type] ?? 0) + 1 };
      const confidenceSum = prev.confidenceSum + shot.confidence;

      const now = Date.now();
      const bucket = rateBucketRef.current;
      let rateHistory = [...prev.rateHistory];
      if (now - bucket.t >= 10000) {
        rateHistory = [...rateHistory, { t: bucket.t, count: bucket.count }].slice(-20);
        rateBucketRef.current = { t: now, count: 1 };
      } else {
        rateBucketRef.current.count++;
      }

      return {
        total,
        byType,
        avgConfidence: confidenceSum / total,
        confidenceSum,
        rateHistory,
        lastShot: shot,
      };
    });
  }

  useEffect(
    () => () => {
      clearInterval(pingIntervalRef.current);
      wsRef.current?.close();
    },
    []
  );

  return {
    status,
    sessionId,
    shots,
    stats,
    syncOffset,
    error,
    startSession,
    stopSession,
    reset,
    triggerCalibration,
  };
}
