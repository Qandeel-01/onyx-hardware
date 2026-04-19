// LiveAnalysisDashboard.jsx
// Live Analysis page for Project ONYX.
// Composition:
//   <LiveAnalysisDashboard sessionId={id} />
// assumes tailwind is configured; swap classes for your styling system as needed.

import React, { createContext, useContext, useMemo, useRef, useState, useEffect } from 'react';
import { useSessionWebSocket } from './useSessionWebSocket';

// ---------------------------------------------------------------------
// Context
// ---------------------------------------------------------------------
const SessionContext = createContext(null);
const useSession = () => {
    const ctx = useContext(SessionContext);
    if (!ctx) throw new Error('useSession must be used inside <LiveAnalysisDashboard>');
    return ctx;
};

// =====================================================================
// Top-level page
// =====================================================================
export default function LiveAnalysisDashboard({ sessionId, authToken }) {
    const ws = useSessionWebSocket(sessionId, { authToken });
    const videoRef = useRef(null);
    const [videoState, setVideoState] = useState({
        recording: false,
        startedAtUtcMs: null,
        stream: null,
        fps: 30,
        resolution: '1280x720',
    });
    const [calibration, setCalibration] = useState({
        clockSynced: false,
        flashCalibrated: false,
        courtCorners: null,
        residualOffsetMs: null,
    });

    // Track clock sync completeness
    useEffect(() => {
        if (ws.syncQuality && ws.offsetHistory.length >= 3) {
            setCalibration(c => ({ ...c, clockSynced: ws.syncQuality !== 'poor' }));
        }
    }, [ws.syncQuality, ws.offsetHistory.length]);

    const contextValue = useMemo(() => ({
        sessionId,
        ws,
        videoRef,
        videoState, setVideoState,
        calibration, setCalibration,
    }), [sessionId, ws, videoState, calibration]);

    const sessionReady =
        calibration.clockSynced &&
        calibration.flashCalibrated &&
        calibration.courtCorners != null;

    return (
        <SessionContext.Provider value={contextValue}>
            <div className="min-h-screen bg-slate-950 text-slate-100">
                <SessionStatusBar />
                {!sessionReady && <CalibrationPanel />}
                {sessionReady && (
                    <>
                        <div className="grid grid-cols-12 gap-4 p-4">
                            <div className="col-span-7"><VideoFeedPanel /></div>
                            <div className="col-span-5"><LiveStatsPanel /></div>
                        </div>
                        <ShotTimeline />
                    </>
                )}
            </div>
        </SessionContext.Provider>
    );
}

// =====================================================================
// Top status bar
// =====================================================================
function SessionStatusBar() {
    const { ws, sessionId } = useSession();
    const qualityColor = {
        good: 'bg-emerald-500', fair: 'bg-amber-500', poor: 'bg-red-500', null: 'bg-slate-500',
    }[ws.syncQuality ?? 'null'];

    return (
        <header className="flex items-center justify-between border-b border-slate-800 px-4 py-2 text-sm">
            <div className="flex items-center gap-3">
                <span className="font-mono text-slate-400">Session #{sessionId}</span>
                <StatusPill label={`WS: ${ws.status}`} ok={ws.status === 'connected'} />
                <StatusPill label={`Device: ${ws.deviceStatus ? 'linked' : '—'}`} ok={!!ws.deviceStatus} />
                <div className="flex items-center gap-1">
                    <span className={`inline-block h-2 w-2 rounded-full ${qualityColor}`} />
                    <span className="text-xs text-slate-400">
                        sync {ws.syncQuality ?? '—'} · {ws.rttMs != null ? `${ws.rttMs.toFixed(0)}ms RTT` : 'waiting'}
                    </span>
                </div>
            </div>
            <div className="text-xs text-slate-500">
                offset: {ws.offsetMs != null ? `${ws.offsetMs.toFixed(1)}ms` : '—'}
            </div>
        </header>
    );
}

function StatusPill({ label, ok }) {
    return (
        <span className={`rounded px-2 py-0.5 text-xs ${ok ? 'bg-emerald-900 text-emerald-200' : 'bg-slate-800 text-slate-400'}`}>
            {label}
        </span>
    );
}

// =====================================================================
// Calibration panel (gate to enter live mode)
// =====================================================================
function CalibrationPanel() {
    const { calibration, setCalibration, ws, sessionId } = useSession();

    const runFlashCalibration = async () => {
        // Tell wearable to fire the 3-pulse flash sequence
        ws.send({ type: 'calibration_flash_request', session_id: sessionId });
        // Backend will run the brightness detector on the current video buffer
        // and POST back residual_offset_ms
        // Here we simulate — replace with real polling or push notification:
        setTimeout(() => {
            setCalibration(c => ({ ...c, flashCalibrated: true, residualOffsetMs: 4.2 }));
        }, 6000);
    };

    return (
        <div className="mx-auto max-w-3xl space-y-4 p-8">
            <h1 className="text-2xl font-semibold">Session Setup</h1>
            <p className="text-sm text-slate-400">Complete all four steps before starting.</p>

            <CalibChecklistItem
                done={ws.status === 'connected'}
                label="Wearable connected"
                detail={ws.deviceStatus ? `FW ${ws.deviceStatus.firmware ?? '?'}, batt ${ws.deviceStatus.battery ?? '?'}%` : 'waiting...'}
            />
            <CalibChecklistItem
                done={calibration.clockSynced}
                label="Clock synchronized"
                detail={`${ws.offsetHistory.length} samples · ${ws.syncQuality ?? 'measuring'}`}
            />
            <CalibChecklistItem
                done={calibration.courtCorners != null}
                label="Court corners marked"
                detail={calibration.courtCorners ? 'homography ready' : 'click corners on video preview'}
                action={<button
                    onClick={() => setCalibration(c => ({ ...c, courtCorners: [[0,0],[1,0],[1,1],[0,1]] }))}
                    className="rounded bg-slate-700 px-3 py-1 text-xs hover:bg-slate-600">
                    Mark Corners
                </button>}
            />
            <CalibChecklistItem
                done={calibration.flashCalibrated}
                label="Hardware flash alignment"
                detail={calibration.flashCalibrated
                    ? `residual ${calibration.residualOffsetMs?.toFixed(1)}ms`
                    : 'runs 3 LED pulses, locks device→video offset to ±1 frame'}
                action={!calibration.flashCalibrated && (
                    <button
                        onClick={runFlashCalibration}
                        disabled={!calibration.clockSynced || calibration.courtCorners == null}
                        className="rounded bg-indigo-600 px-3 py-1 text-xs disabled:opacity-40 hover:bg-indigo-500">
                        Run Flash Sync
                    </button>
                )}
            />
        </div>
    );
}

function CalibChecklistItem({ done, label, detail, action }) {
    return (
        <div className="flex items-center justify-between rounded border border-slate-800 bg-slate-900/50 p-3">
            <div className="flex items-center gap-3">
                <div className={`h-5 w-5 rounded-full flex items-center justify-center text-xs
                    ${done ? 'bg-emerald-600' : 'bg-slate-700'}`}>
                    {done ? '✓' : ''}
                </div>
                <div>
                    <div className="text-sm font-medium">{label}</div>
                    <div className="text-xs text-slate-500">{detail}</div>
                </div>
            </div>
            {action}
        </div>
    );
}

// =====================================================================
// Video feed panel
// =====================================================================
function VideoFeedPanel() {
    const { videoRef, videoState, setVideoState, sessionId } = useSession();

    const startRecording = async () => {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({
                video: { width: 1280, height: 720, frameRate: 30 },
                audio: false,
            });
            if (videoRef.current) videoRef.current.srcObject = stream;

            // Call backend to stamp recording start against server UTC
            const clientTs = Date.now();
            const res = await fetch(`/api/sessions/${sessionId}/video/start`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ client_ts_ms: clientTs }),
            });
            const { server_ts_ms, rtt_ms } = await res.json();
            const startedAtUtcMs = server_ts_ms - rtt_ms / 2;

            setVideoState({ ...videoState, recording: true, startedAtUtcMs, stream });
        } catch (e) {
            console.error('video start failed', e);
        }
    };

    const stopRecording = () => {
        videoState.stream?.getTracks().forEach(t => t.stop());
        setVideoState({ ...videoState, recording: false, stream: null });
    };

    return (
        <div className="rounded-lg border border-slate-800 bg-slate-900/50 p-3">
            <div className="relative aspect-video w-full overflow-hidden rounded bg-black">
                <video ref={videoRef} autoPlay muted playsInline className="h-full w-full object-cover" />
                {!videoState.recording && (
                    <div className="absolute inset-0 flex items-center justify-center text-slate-500">
                        <span className="text-sm">Video feed placeholder</span>
                    </div>
                )}
                <CourtOverlay />
            </div>
            <div className="mt-3 flex items-center justify-between">
                <div className="text-xs text-slate-500">
                    {videoState.recording
                        ? `● REC · started ${new Date(videoState.startedAtUtcMs).toLocaleTimeString()}`
                        : 'idle'}
                </div>
                {videoState.recording
                    ? <button onClick={stopRecording} className="rounded bg-red-600 px-3 py-1 text-sm hover:bg-red-500">Stop</button>
                    : <button onClick={startRecording} className="rounded bg-emerald-600 px-3 py-1 text-sm hover:bg-emerald-500">Start Recording</button>}
            </div>
        </div>
    );
}

// Live overlay showing last shot position / court rails
function CourtOverlay() {
    const { ws } = useSession();
    const last = ws.lastShot;
    if (!last) return null;
    return (
        <svg className="pointer-events-none absolute inset-0 h-full w-full">
            {/* Last shot marker — position placeholder since CV runs post-hoc */}
            <circle cx="50%" cy="50%" r="8" fill="rgba(99,102,241,0.6)" />
            <text x="52%" y="49%" fill="#fff" fontSize="11" fontFamily="monospace">
                {last.shot_type}
            </text>
        </svg>
    );
}

// =====================================================================
// Live stats panel
// =====================================================================
function LiveStatsPanel() {
    const { ws } = useSession();

    // Derive stats from shot stream
    const stats = useMemo(() => {
        const counts = {};
        for (const s of ws.shots) counts[s.shot_type] = (counts[s.shot_type] ?? 0) + 1;
        return { total: ws.shots.length, byType: counts };
    }, [ws.shots]);

    return (
        <div className="space-y-3">
            <CurrentShotCard shot={ws.lastShot} />
            <ShotCounter total={stats.total} />
            <ShotDistribution byType={stats.byType} />
            <RallyTracker shots={ws.shots} />
            <TelemetryPanel />
        </div>
    );
}

function CurrentShotCard({ shot }) {
    return (
        <div className="rounded-lg border border-slate-800 bg-gradient-to-br from-indigo-900/40 to-slate-900 p-4">
            <div className="text-xs uppercase tracking-wide text-slate-400">Current Shot</div>
            <div className="mt-2 text-3xl font-semibold">
                {shot ? shot.shot_type : '—'}
            </div>
            <div className="mt-1 text-xs text-slate-500">
                {shot && `confidence ${(shot.confidence * 100).toFixed(0)}% · ${Math.round((Date.now() - shot.receivedAt) / 1000)}s ago`}
            </div>
        </div>
    );
}

function ShotCounter({ total }) {
    return (
        <div className="rounded-lg border border-slate-800 bg-slate-900/50 p-4">
            <div className="text-xs uppercase tracking-wide text-slate-400">Total Shots</div>
            <div className="mt-2 text-3xl font-mono">{total}</div>
        </div>
    );
}

function ShotDistribution({ byType }) {
    const entries = Object.entries(byType).sort((a, b) => b[1] - a[1]);
    const max = Math.max(1, ...entries.map(e => e[1]));
    return (
        <div className="rounded-lg border border-slate-800 bg-slate-900/50 p-4">
            <div className="text-xs uppercase tracking-wide text-slate-400 mb-2">Distribution</div>
            {entries.length === 0 && <div className="text-sm text-slate-500">no shots yet</div>}
            {entries.map(([type, n]) => (
                <div key={type} className="mb-1">
                    <div className="flex justify-between text-xs">
                        <span>{type}</span><span className="font-mono">{n}</span>
                    </div>
                    <div className="h-1.5 rounded bg-slate-800">
                        <div className="h-full rounded bg-indigo-500" style={{ width: `${(n / max) * 100}%` }} />
                    </div>
                </div>
            ))}
        </div>
    );
}

function RallyTracker({ shots }) {
    // Simple: count shots within last 15s window as an approximation
    const now = Date.now();
    const recent = shots.filter(s => now - (s.receivedAt ?? 0) < 15000);
    return (
        <div className="rounded-lg border border-slate-800 bg-slate-900/50 p-4">
            <div className="text-xs uppercase tracking-wide text-slate-400">Current Rally</div>
            <div className="mt-2 text-2xl font-mono">{recent.length} shots</div>
        </div>
    );
}

function TelemetryPanel() {
    const { ws } = useSession();
    return (
        <div className="rounded-lg border border-slate-800 bg-slate-900/50 p-4 text-xs font-mono text-slate-400">
            <div>RTT:        {ws.rttMs != null ? `${ws.rttMs.toFixed(1)} ms` : '—'}</div>
            <div>Offset:     {ws.offsetMs != null ? `${ws.offsetMs.toFixed(2)} ms` : '—'}</div>
            <div>Sync count: {ws.offsetHistory.length}</div>
            <div>Last sync:  {ws.lastSyncAt ? `${Math.round((Date.now() - ws.lastSyncAt) / 1000)}s ago` : '—'}</div>
        </div>
    );
}

// =====================================================================
// Horizontal shot timeline
// =====================================================================
function ShotTimeline() {
    const { ws, videoState } = useSession();
    if (!videoState.startedAtUtcMs) return null;

    const now = Date.now();
    const elapsed = (now - videoState.startedAtUtcMs) / 1000;

    return (
        <div className="mx-4 mb-4 rounded-lg border border-slate-800 bg-slate-900/50 p-3">
            <div className="mb-2 flex justify-between text-xs text-slate-400">
                <span>Shot Timeline</span>
                <span className="font-mono">{elapsed.toFixed(1)}s</span>
            </div>
            <div className="relative h-10 w-full overflow-hidden rounded bg-slate-800">
                {ws.shots.map((s, i) => {
                    const t = (s.receivedAt - videoState.startedAtUtcMs) / 1000;
                    const pct = Math.max(0, Math.min(100, (t / Math.max(elapsed, 1)) * 100));
                    return (
                        <div
                            key={i}
                            title={`${s.shot_type} @ ${t.toFixed(1)}s`}
                            className="absolute top-0 h-full w-0.5 bg-indigo-400"
                            style={{ left: `${pct}%` }}
                        />
                    );
                })}
            </div>
        </div>
    );
}
