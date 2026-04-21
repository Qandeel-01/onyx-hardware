/**
 * useOnyxSession
 * Manages the full lifecycle: POST /api/sessions → WS /ws/shots/{id} → SYNC_PING/PONG
 * Matches ws_shots.py message protocol exactly.
 */
import { useState, useEffect, useRef, useCallback } from 'react';

const API_BASE = 'http://localhost:8000';
const WS_BASE  = 'ws://localhost:8000';

const INITIAL_STATS = {
  total: 0,
  byType: { Forehand: 0, Backhand: 0, Smash: 0, Volley: 0, Bandeja: 0, Lob: 0 },
  avgConfidence: 0,
  confidenceSum: 0,
  rateHistory: [],   // { t: Date, count: number } buckets per 10s
  lastShot: null,
};

export function useOnyxSession() {
  const [status, setStatus]         = useState('idle');   // idle | creating | connected | error | stopped
  const [sessionId, setSessionId]   = useState(null);
  const [shots, setShots]           = useState([]);        // last 50 shots for timeline
  const [stats, setStats]           = useState(INITIAL_STATS);
  const [syncOffset, setSyncOffset] = useState(null);      // ms delta from SYNC_PONG
  const [error, setError]           = useState(null);

  const wsRef            = useRef(null);
  const pingIntervalRef  = useRef(null);
  const rateBucketRef    = useRef({ t: Date.now(), count: 0 });
  const statsRef         = useRef(INITIAL_STATS);  // mutable ref for accumulation

  // ── Create session via REST, then open WebSocket ──────────────────
  const startSession = useCallback(async (fps = 30) => {
    setStatus('creating');
    setError(null);

    let sid;
    try {
      const res = await fetch(`${API_BASE}/api/sessions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ fps }),
      });
      if (!res.ok) {
        const body = await res.text();
        throw new Error(`POST /api/sessions ${res.status}: ${body}`);
      }
      const data = await res.json();
      sid = data.id;
      setSessionId(sid);
    } catch (e) {
      setError(e.message);
      setStatus('error');
      return;
    }

    // ── Open WebSocket ────────────────────────────────────────────
    const ws = new WebSocket(`${WS_BASE}/ws/shots/${sid}`);
    wsRef.current = ws;

    ws.onopen = () => {
      setStatus('connected');
      // Start clock-sync ping every 5s
      _sendPing(ws);
      pingIntervalRef.current = setInterval(() => _sendPing(ws), 5000);
    };

    ws.onmessage = (evt) => {
      let msg;
      try { msg = JSON.parse(evt.data); } catch { return; }

      if (msg.type === 'SYNC_PONG') {
        // rtt = now - echo_browser_ts; offset = server_ts - (browser_ts + rtt/2)
        const now = Date.now();
        const rtt  = now - (msg.echo_browser_ts ?? now);
        const offset = msg.device_ts - (msg.echo_browser_ts + rtt / 2);
        setSyncOffset({ rtt_ms: rtt, offset_ms: offset });
        return;
      }

      if (msg.type === 'SHOT_EVENT') {
        _handleShot(msg);
        return;
      }

      if (msg.type === 'ERROR') {
        console.error('[ONYX WS]', msg.message);
        setError(msg.message);
      }
    };

    ws.onerror = () => {
      setError(`WebSocket error — is uvicorn running on port 8000? (ws://localhost:8000/ws/shots/${sid})`);
      setStatus('error');
    };

    ws.onclose = (evt) => {
      clearInterval(pingIntervalRef.current);
      if (evt.code === 4004) {
        setError('Session not found on server (4004). Create a new session.');
      }
      if (status !== 'stopped') setStatus('stopped');
    };
  }, []);  // eslint-disable-line

  // ── Stop session ─────────────────────────────────────────────────
  const stopSession = useCallback(async () => {
    clearInterval(pingIntervalRef.current);
    wsRef.current?.close();
    wsRef.current = null;
    setStatus('stopped');

    if (sessionId) {
      // PATCH ended_at
      await fetch(`${API_BASE}/api/sessions/${sessionId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ended_at: new Date().toISOString() }),
      }).catch(() => {});
    }
  }, [sessionId]);

  // ── Reset everything ─────────────────────────────────────────────
  const reset = useCallback(() => {
    stopSession();
    setSessionId(null);
    setShots([]);
    setStats(INITIAL_STATS);
    statsRef.current = INITIAL_STATS;
    setSyncOffset(null);
    setError(null);
    setStatus('idle');
    rateBucketRef.current = { t: Date.now(), count: 0 };
  }, [stopSession]);

  // ── Clock calibration POST ────────────────────────────────────────
  const triggerCalibration = useCallback(async () => {
    if (!sessionId || !syncOffset) return null;
    const res = await fetch(
      `${API_BASE}/api/sessions/${sessionId}/calibrations?rtt_ms=${syncOffset.rtt_ms.toFixed(2)}&offset_ms=${syncOffset.offset_ms.toFixed(2)}`,
      { method: 'POST' }
    );
    return res.ok ? res.json() : null;
  }, [sessionId, syncOffset]);

  // ── Internal helpers ──────────────────────────────────────────────
  function _sendPing(ws) {
    if (ws.readyState !== WebSocket.OPEN) return;
    ws.send(JSON.stringify({ type: 'SYNC_PING', browser_ts: Date.now() }));
  }

  function _handleShot(msg) {
    const shot = {
      id:          msg.id,
      type:        msg.shot_type,
      confidence:  msg.confidence,
      device_ts:   msg.device_ts_ms,
      timestamp:   msg.timestamp,
      wall_ts:     Date.now(),
      accel:       { x: msg.accel_x, y: msg.accel_y, z: msg.accel_z },
      gyro:        { x: msg.gyro_x,  y: msg.gyro_y,  z: msg.gyro_z  },
    };

    // Update shots timeline (keep last 50)
    setShots(prev => [shot, ...prev].slice(0, 50));

    // Update stats
    setStats(prev => {
      const total = prev.total + 1;
      const byType = { ...prev.byType, [shot.type]: (prev.byType[shot.type] ?? 0) + 1 };
      const confidenceSum = prev.confidenceSum + shot.confidence;

      // Rate bucket (10s windows)
      const now = Date.now();
      let rateHistory = [...prev.rateHistory];
      const bucket = rateBucketRef.current;
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

  // Cleanup on unmount
  useEffect(() => () => {
    clearInterval(pingIntervalRef.current);
    wsRef.current?.close();
  }, []);

  return {
    status,       // 'idle' | 'creating' | 'connected' | 'error' | 'stopped'
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
