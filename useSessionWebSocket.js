// useSessionWebSocket.js
// WebSocket hook for Project ONYX live analysis.
// Responsibilities:
//   - Persistent WS connection with auto-reconnect and heartbeat
//   - SNTP-style clock sync loop (10 samples/batch, every 30s)
//   - Exposes min-RTT offset estimate + quality metrics
//   - Forwards typed events (shot_event, device_status, calibration_flash)
//
// Usage:
//   const { status, offsetMs, syncQuality, shots, send } =
//       useSessionWebSocket(sessionId, { wsUrl: 'wss://api.onyx.local/ws' });

import { useEffect, useReducer, useRef, useCallback } from 'react';

// ---------------------------------------------------------------------
// Tunables
// ---------------------------------------------------------------------
const SYNC_SAMPLES_PER_BATCH = 10;
const SYNC_INTERVAL_MS       = 30_000;
const SYNC_SAMPLE_SPACING_MS = 80;
const HEARTBEAT_INTERVAL_MS  = 10_000;
const RECONNECT_BASE_MS      = 500;
const RECONNECT_MAX_MS       = 15_000;

// ---------------------------------------------------------------------
// Reducer for stream state
// ---------------------------------------------------------------------
const initialState = {
    status: 'idle',                 // idle | connecting | connected | reconnecting | closed
    offsetMs: null,                  // authoritative device→server offset
    offsetHistory: [],               // recent offsets for drift tracking
    rttMs: null,
    syncQuality: null,               // 'good' | 'fair' | 'poor' | null
    lastSyncAt: null,
    deviceStatus: null,              // { battery, rssi, firmware }
    shots: [],                       // full list for the session (UI can windowize)
    lastShot: null,
    errors: [],
};

function reducer(state, action) {
    switch (action.type) {
        case 'STATUS':
            return { ...state, status: action.status };

        case 'SYNC_RESULT': {
            const { offsetMs, rttMs } = action;
            const history = [...state.offsetHistory, { t: Date.now(), offsetMs, rttMs }].slice(-20);
            const quality =
                rttMs < 30 ? 'good' :
                rttMs < 80 ? 'fair' : 'poor';
            return {
                ...state,
                offsetMs,
                rttMs,
                syncQuality: quality,
                lastSyncAt: Date.now(),
                offsetHistory: history,
            };
        }

        case 'DEVICE_STATUS':
            return { ...state, deviceStatus: action.payload };

        case 'SHOT_EVENT': {
            const shot = action.payload;
            return {
                ...state,
                shots: [...state.shots, shot],
                lastShot: shot,
            };
        }

        case 'ERROR':
            return { ...state, errors: [...state.errors, action.error].slice(-10) };

        case 'RESET':
            return initialState;

        default:
            return state;
    }
}

// ---------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------
export function useSessionWebSocket(sessionId, options = {}) {
    const {
        wsUrl = import.meta?.env?.VITE_ONYX_WS_URL ?? 'wss://api.onyx.local/ws',
        authToken,
        autoSync = true,
    } = options;

    const [state, dispatch] = useReducer(reducer, initialState);

    // Mutable refs for things we don't want to re-render on
    const wsRef           = useRef(null);
    const reconnectRef    = useRef({ attempts: 0, timer: null });
    const heartbeatRef    = useRef(null);
    const syncRef         = useRef({ timer: null, sampleTimer: null, batch: [] });
    const pendingSyncsRef = useRef(new Map()); // t1 → resolver (for request/response matching)

    // -------------------------------------------------------------
    // Message dispatch
    // -------------------------------------------------------------
    const handleMessage = useCallback((raw) => {
        let msg;
        try { msg = JSON.parse(raw); }
        catch (e) {
            dispatch({ type: 'ERROR', error: `bad json: ${e.message}` });
            return;
        }

        switch (msg.type) {
            case 'sync_response': {
                const { t1_device_ms, t2_server_utc_ms, t3_server_utc_ms } = msg;
                const t4 = performance.timeOrigin + performance.now();
                const record = pendingSyncsRef.current.get(t1_device_ms);
                if (record) {
                    pendingSyncsRef.current.delete(t1_device_ms);
                    const rtt    = (t4 - t1_device_ms) - (t3_server_utc_ms - t2_server_utc_ms);
                    const offset = ((t2_server_utc_ms - t1_device_ms) + (t3_server_utc_ms - t4)) / 2;
                    syncRef.current.batch.push({ t1: t1_device_ms, rtt, offset });
                }
                break;
            }
            case 'shot_event':
                dispatch({ type: 'SHOT_EVENT', payload: msg });
                break;
            case 'device_status':
                dispatch({ type: 'DEVICE_STATUS', payload: msg });
                break;
            case 'pong':
                // heartbeat ack — nothing to do
                break;
            case 'error':
                dispatch({ type: 'ERROR', error: msg.message ?? 'server error' });
                break;
            default:
                // silently ignore unknown types (forward-compatible)
                break;
        }
    }, []);

    // -------------------------------------------------------------
    // Clock sync batch — 10 samples spaced 80ms apart, keep min-RTT
    // -------------------------------------------------------------
    const runSyncBatch = useCallback(() => {
        if (wsRef.current?.readyState !== WebSocket.OPEN) return;
        syncRef.current.batch = [];
        let sent = 0;

        const sendOne = () => {
            if (sent >= SYNC_SAMPLES_PER_BATCH) {
                // Finalize: pick min-RTT sample
                const samples = syncRef.current.batch;
                if (samples.length === 0) return;
                const best = samples.reduce((a, b) => (a.rtt < b.rtt ? a : b));
                dispatch({ type: 'SYNC_RESULT', offsetMs: best.offset, rttMs: best.rtt });

                // Also tell the server which was selected — useful for audit
                wsRef.current?.send(JSON.stringify({
                    type: 'sync_batch_finalized',
                    session_id: sessionId,
                    selected_t1_device_ms: best.t1,
                    sample_count: samples.length,
                }));
                return;
            }
            const t1 = performance.timeOrigin + performance.now();
            pendingSyncsRef.current.set(t1, true);
            wsRef.current.send(JSON.stringify({
                type: 'sync_request',
                session_id: sessionId,
                t1_device_ms: t1,
            }));
            sent++;
            syncRef.current.sampleTimer = setTimeout(sendOne, SYNC_SAMPLE_SPACING_MS);
        };

        sendOne();
    }, [sessionId]);

    // -------------------------------------------------------------
    // Connection lifecycle
    // -------------------------------------------------------------
    const connect = useCallback(() => {
        dispatch({ type: 'STATUS', status: 'connecting' });
        const url = new URL(wsUrl);
        url.searchParams.set('session_id', String(sessionId));
        if (authToken) url.searchParams.set('token', authToken);

        const ws = new WebSocket(url.toString());
        wsRef.current = ws;

        ws.onopen = () => {
            dispatch({ type: 'STATUS', status: 'connected' });
            reconnectRef.current.attempts = 0;

            // Heartbeat
            heartbeatRef.current = setInterval(() => {
                if (ws.readyState === WebSocket.OPEN) {
                    ws.send(JSON.stringify({ type: 'ping', ts: Date.now() }));
                }
            }, HEARTBEAT_INTERVAL_MS);

            // Clock sync
            if (autoSync) {
                runSyncBatch();
                syncRef.current.timer = setInterval(runSyncBatch, SYNC_INTERVAL_MS);
            }
        };

        ws.onmessage = (ev) => handleMessage(ev.data);

        ws.onerror = (ev) => {
            dispatch({ type: 'ERROR', error: 'websocket error' });
        };

        ws.onclose = () => {
            cleanupTimers();
            // Exponential backoff reconnect
            const attempts = ++reconnectRef.current.attempts;
            const delay = Math.min(RECONNECT_BASE_MS * 2 ** attempts, RECONNECT_MAX_MS);
            dispatch({ type: 'STATUS', status: 'reconnecting' });
            reconnectRef.current.timer = setTimeout(connect, delay);
        };
    }, [sessionId, wsUrl, authToken, autoSync, runSyncBatch, handleMessage]);

    const cleanupTimers = () => {
        if (heartbeatRef.current)        clearInterval(heartbeatRef.current);
        if (syncRef.current.timer)       clearInterval(syncRef.current.timer);
        if (syncRef.current.sampleTimer) clearTimeout(syncRef.current.sampleTimer);
        heartbeatRef.current = null;
        syncRef.current.timer = null;
        syncRef.current.sampleTimer = null;
    };

    // -------------------------------------------------------------
    // Public send: serialize + guard
    // -------------------------------------------------------------
    const send = useCallback((payload) => {
        if (wsRef.current?.readyState === WebSocket.OPEN) {
            wsRef.current.send(JSON.stringify(payload));
            return true;
        }
        return false;
    }, []);

    // -------------------------------------------------------------
    // Mount / unmount
    // -------------------------------------------------------------
    useEffect(() => {
        if (!sessionId) return;
        connect();
        return () => {
            cleanupTimers();
            if (reconnectRef.current.timer) clearTimeout(reconnectRef.current.timer);
            wsRef.current?.close();
            dispatch({ type: 'RESET' });
        };
    }, [sessionId, connect]);

    return {
        status:        state.status,
        offsetMs:      state.offsetMs,
        offsetHistory: state.offsetHistory,
        rttMs:         state.rttMs,
        syncQuality:   state.syncQuality,
        lastSyncAt:    state.lastSyncAt,
        deviceStatus:  state.deviceStatus,
        shots:         state.shots,
        lastShot:      state.lastShot,
        errors:        state.errors,
        send,
    };
}
