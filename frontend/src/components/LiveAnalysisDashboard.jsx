/**
 * LiveAnalysisDashboard — Project ONYX
 * Drop this anywhere in your Vite/React project.
 *
 * Dependencies:
 *   npm install recharts
 *
 * Internal deps (in this repo):
 *   src/hooks/useOnyxSession.js
 *   src/components/OnyxCharts.jsx
 *
 * Usage:
 *   import LiveAnalysisDashboard from './components/LiveAnalysisDashboard';
 *   <LiveAnalysisDashboard />
 */
import { useState, useRef, useEffect, useCallback } from 'react';
import { useOnyxSession } from '../hooks/useOnyxSession';
import { DistributionChart, RateChart, ConfidenceChart } from './OnyxCharts';

// ── Styles ────────────────────────────────────────────────────────────────────
const css = `
  @import url('https://fonts.googleapis.com/css2?family=DM+Mono:ital,wght@0,400;0,500;1,400&family=Syne:wght@400;600;700;800&display=swap');

  .onyx-root {
    --onyx-bg:       #090b0f;
    --onyx-surface:  #0f1117;
    --onyx-surface2: #161921;
    --onyx-border:   rgba(255,255,255,0.07);
    --onyx-border2:  rgba(255,255,255,0.12);
    --onyx-accent:   #00e5a0;
    --onyx-blue:     #4f8cff;
    --onyx-warn:     #ffb347;
    --onyx-danger:   #ff5c5c;
    --onyx-text:     #dde1ea;
    --onyx-muted:    #555c6e;
    --onyx-head:     'Syne', sans-serif;
    --onyx-mono:     'DM Mono', monospace;

    background:  var(--onyx-bg);
    color:       var(--onyx-text);
    font-family: var(--onyx-head);
    min-height:  100vh;
    padding:     20px;
    box-sizing:  border-box;
  }

  .onyx-root * { box-sizing: border-box; margin: 0; padding: 0; }

  /* ── Top bar ── */
  .onyx-topbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding-bottom: 16px;
    border-bottom: 0.5px solid var(--onyx-border);
    margin-bottom: 16px;
  }
  .onyx-logo { font-size: 20px; font-weight: 800; letter-spacing: 0.1em; color: var(--onyx-accent); }
  .onyx-logo span { color: var(--onyx-text); font-weight: 400; }
  .onyx-status-row { display: flex; align-items: center; gap: 10px; }
  .onyx-timer { font-family: var(--onyx-mono); font-size: 14px; color: var(--onyx-muted); min-width: 72px; text-align: right; }

  /* ── Pills ── */
  .onyx-pill {
    display: flex; align-items: center; gap: 5px;
    font-family: var(--onyx-mono); font-size: 10px;
    padding: 3px 10px; border-radius: 20px; border: 0.5px solid;
  }
  .onyx-pill-dot { width: 5px; height: 5px; border-radius: 50%; }
  .pill-idle    { border-color: var(--onyx-muted);   color: var(--onyx-muted);   }
  .pill-idle    .onyx-pill-dot { background: var(--onyx-muted);   }
  .pill-live    { border-color: var(--onyx-accent);  color: var(--onyx-accent);  }
  .pill-live    .onyx-pill-dot { background: var(--onyx-accent);  animation: onyxBlink 1s infinite; }
  .pill-error   { border-color: var(--onyx-danger);  color: var(--onyx-danger);  }
  .pill-error   .onyx-pill-dot { background: var(--onyx-danger);  }
  .pill-stopped { border-color: var(--onyx-warn);    color: var(--onyx-warn);    }
  .pill-stopped .onyx-pill-dot { background: var(--onyx-warn);    }

  @keyframes onyxBlink { 0%,100%{opacity:1} 50%{opacity:0.2} }

  /* ── Error banner ── */
  .onyx-error-banner {
    background: rgba(255,92,92,0.07);
    border: 0.5px solid var(--onyx-danger);
    border-radius: 8px;
    padding: 10px 14px;
    font-family: var(--onyx-mono);
    font-size: 11px;
    color: var(--onyx-danger);
    margin-bottom: 14px;
  }

  /* ── Calibration banner ── */
  .onyx-calib-banner {
    display: flex; align-items: center; gap: 12px;
    background: rgba(255,179,71,0.06);
    border: 0.5px solid var(--onyx-warn);
    border-radius: 8px;
    padding: 9px 14px;
    font-family: var(--onyx-mono);
    font-size: 11px;
    color: var(--onyx-warn);
    margin-bottom: 14px;
  }
  .onyx-calib-bar { flex:1; height:3px; background:rgba(255,179,71,0.15); border-radius:2px; overflow:hidden; }
  .onyx-calib-fill { height:100%; background:var(--onyx-warn); border-radius:2px; transition:width .12s linear; }

  /* ── Main grid ── */
  .onyx-grid { display: grid; grid-template-columns: 300px 1fr; gap: 14px; }
  @media (max-width: 900px) { .onyx-grid { grid-template-columns: 1fr; } }

  .onyx-left  { display: flex; flex-direction: column; gap: 12px; }
  .onyx-right { display: flex; flex-direction: column; gap: 12px; }

  /* ── Camera box ── */
  .onyx-cam {
    background: var(--onyx-surface);
    border: 0.5px solid var(--onyx-border);
    border-radius: 10px;
    overflow: hidden;
    position: relative;
    aspect-ratio: 16/10;
  }
  .onyx-cam video { width:100%; height:100%; object-fit:cover; display:block; }
  .onyx-cam-overlay {
    position: absolute; inset: 0;
    display: flex; flex-direction: column;
    align-items: center; justify-content: center; gap: 10px;
    background: rgba(9,11,15,0.9);
  }
  .onyx-cam-hint { font-family:var(--onyx-mono); font-size:11px; color:var(--onyx-muted); }
  .onyx-cam-btns { display:flex; gap:8px; flex-wrap:wrap; justify-content:center; }
  .onyx-ip-row { display:flex; gap:6px; width:100%; padding:0 14px; }
  .onyx-ip-row input {
    flex:1; background:rgba(255,255,255,0.04);
    border:0.5px solid var(--onyx-border2); border-radius:6px;
    color:var(--onyx-text); font-family:var(--onyx-mono); font-size:10px;
    padding:6px 10px; outline:none;
  }
  .onyx-ip-row input::placeholder { color:var(--onyx-muted); }
  .onyx-ip-row input:focus { border-color:var(--onyx-blue); }
  .onyx-shot-flash {
    position:absolute; bottom:8px; left:8px;
    font-family:var(--onyx-mono); font-size:11px;
    padding:4px 12px; border-radius:5px;
    border:0.5px solid; pointer-events:none;
    transition:opacity 0.3s;
  }

  /* ── Metric cards ── */
  .onyx-metrics { display:grid; grid-template-columns:1fr 1fr; gap:8px; }
  .onyx-metric {
    background:var(--onyx-surface); border:0.5px solid var(--onyx-border);
    border-radius:8px; padding:10px 12px;
  }
  .onyx-metric-label {
    font-family:var(--onyx-mono); font-size:9px; text-transform:uppercase;
    letter-spacing:0.1em; color:var(--onyx-muted); margin-bottom:4px;
  }
  .onyx-metric-value { font-size:24px; font-weight:700; line-height:1; }
  .onyx-metric-sub { font-family:var(--onyx-mono); font-size:9px; color:var(--onyx-muted); margin-top:3px; }

  /* ── Buttons ── */
  .onyx-btn {
    font-family:var(--onyx-head); font-size:11px; font-weight:700;
    padding:7px 14px; border-radius:6px; border:0.5px solid;
    cursor:pointer; letter-spacing:0.04em; transition:all 0.15s;
    background:transparent;
  }
  .onyx-btn:active { transform:scale(0.97); }
  .onyx-btn-primary  { background:var(--onyx-accent); color:#090b0f; border-color:var(--onyx-accent); }
  .onyx-btn-blue     { color:var(--onyx-blue);   border-color:var(--onyx-blue);   }
  .onyx-btn-ghost    { color:var(--onyx-muted);  border-color:var(--onyx-border2); }
  .onyx-btn-danger   { color:var(--onyx-danger); border-color:var(--onyx-danger); }
  .onyx-btn-warn     { color:var(--onyx-warn);   border-color:var(--onyx-warn);   }
  .onyx-btn:disabled { opacity:0.35; cursor:not-allowed; transform:none; }

  .onyx-ctrl-row { display:flex; gap:8px; flex-wrap:wrap; align-items:center; }

  /* ── Panel ── */
  .onyx-panel {
    background:var(--onyx-surface); border:0.5px solid var(--onyx-border);
    border-radius:10px; padding:14px 16px;
  }
  .onyx-panel-header {
    font-family:var(--onyx-mono); font-size:9px; text-transform:uppercase;
    letter-spacing:0.12em; color:var(--onyx-muted);
    display:flex; align-items:center; justify-content:space-between;
    margin-bottom:12px;
  }
  .onyx-panel-header-ts { font-size:9px; color:var(--onyx-muted); }

  /* ── Shot timeline ── */
  .onyx-timeline { display:flex; flex-direction:column; gap:4px; max-height:180px; overflow-y:auto; }
  .onyx-timeline::-webkit-scrollbar { width:2px; }
  .onyx-timeline::-webkit-scrollbar-thumb { background:var(--onyx-border2); border-radius:2px; }
  .onyx-shot-row {
    display:flex; align-items:center; gap:8px;
    padding:5px 8px; border-radius:5px;
    background:rgba(255,255,255,0.02);
    animation:onyxSlideIn 0.2s ease;
    font-size:11px;
  }
  @keyframes onyxSlideIn { from{opacity:0;transform:translateX(-6px)} to{opacity:1;transform:translateX(0)} }
  .onyx-type-badge {
    font-family:var(--onyx-mono); font-size:9px; font-weight:500;
    padding:2px 8px; border-radius:4px; border:0.5px solid;
    min-width:68px; text-align:center;
  }
  .onyx-conf-bar { flex:1; height:2px; background:rgba(255,255,255,0.05); border-radius:2px; overflow:hidden; max-width:50px; }
  .onyx-conf-fill { height:100%; border-radius:2px; }
  .onyx-shot-meta { font-family:var(--onyx-mono); font-size:9px; color:var(--onyx-muted); margin-left:auto; white-space:nowrap; }
  .onyx-empty { font-family:var(--onyx-mono); font-size:10px; color:var(--onyx-muted); text-align:center; padding:24px 0; }

  /* ── Sync badge ── */
  .onyx-sync-badge {
    font-family:var(--onyx-mono); font-size:9px;
    padding:2px 8px; border-radius:4px;
    border:0.5px solid var(--onyx-blue); color:var(--onyx-blue);
  }

  /* ── 2-col chart row ── */
  .onyx-chart-row { display:grid; grid-template-columns:1fr 1fr; gap:12px; }
  @media (max-width:700px) { .onyx-chart-row { grid-template-columns:1fr; } }
`;

// ── Shot type metadata ──────────────────────────────────────────────────────
const SHOT_META = {
  Forehand: { color: '#00e5a0', bg: 'rgba(0,229,160,0.12)' },
  Backhand: { color: '#4f8cff', bg: 'rgba(79,140,255,0.12)' },
  Smash:    { color: '#ff5c5c', bg: 'rgba(255,92,92,0.12)'  },
  Volley:   { color: '#ffb347', bg: 'rgba(255,179,71,0.12)' },
  Bandeja:  { color: '#b464ff', bg: 'rgba(180,100,255,0.12)'},
  Lob:      { color: '#64dcff', bg: 'rgba(100,220,255,0.12)'},
};

function fmt(n) { return n < 10 ? `0${n}` : `${n}`; }
function fmtTime(isoStr) {
  if (!isoStr) return '—';
  try { return new Date(isoStr).toTimeString().slice(0, 8); } catch { return '—'; }
}

// ── Pill component ──────────────────────────────────────────────────────────
function Pill({ status, label }) {
  const cls = {
    idle: 'pill-idle', creating: 'pill-live', connected: 'pill-live',
    error: 'pill-error', stopped: 'pill-stopped',
  }[status] ?? 'pill-idle';
  return (
    <div className={`onyx-pill ${cls}`}>
      <div className="onyx-pill-dot" />
      <span>{label}</span>
    </div>
  );
}

// ── Main component ──────────────────────────────────────────────────────────
export default function LiveAnalysisDashboard() {
  const {
    status, sessionId, shots, stats, syncOffset, error,
    startSession, stopSession, reset, triggerCalibration,
  } = useOnyxSession();

  const [elapsed, setElapsed]         = useState(0);
  const [showIpInput, setShowIpInput] = useState(false);
  const [camActive, setCamActive]     = useState(false);
  const [calibrating, setCalibrating] = useState(false);
  const [calibPct, setCalibPct]       = useState(0);
  const [flashShot, setFlashShot]     = useState(null);

  const videoRef    = useRef(null);
  const streamRef   = useRef(null);
  const startTsRef  = useRef(null);
  const timerRef    = useRef(null);

  // ── Session timer ────────────────────────────────────────────────
  useEffect(() => {
    if (status === 'connected') {
      startTsRef.current = startTsRef.current ?? Date.now();
      timerRef.current = setInterval(() => {
        setElapsed(Math.floor((Date.now() - startTsRef.current) / 1000));
      }, 1000);
    } else {
      clearInterval(timerRef.current);
      if (status === 'idle') { setElapsed(0); startTsRef.current = null; }
    }
    return () => clearInterval(timerRef.current);
  }, [status]);

  // ── Flash latest shot on video overlay ───────────────────────────
  useEffect(() => {
    if (stats.lastShot) {
      setFlashShot(stats.lastShot);
      const t = setTimeout(() => setFlashShot(null), 1400);
      return () => clearTimeout(t);
    }
  }, [stats.lastShot]);

  const timerStr = `${fmt(Math.floor(elapsed / 3600))}:${fmt(Math.floor((elapsed % 3600) / 60))}:${fmt(elapsed % 60)}`;

  // ── Camera helpers ───────────────────────────────────────────────
  const startWebcam = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { width: 1280, height: 720 }, audio: false });
      streamRef.current = stream;
      if (videoRef.current) videoRef.current.srcObject = stream;
      setCamActive(true);
    } catch (e) {
      alert(`Camera error: ${e.message}`);
    }
  }, []);

  const connectIpCam = useCallback(() => {
    const url = document.getElementById('onyx-ip-input')?.value?.trim();
    if (!url) return;
    if (!url.startsWith('http')) {
      alert('RTSP is not supported directly in browsers.\nUse go2rtc or mediamtx to convert RTSP → HLS/WebRTC, then enter the http:// stream URL.');
      return;
    }
    if (videoRef.current) { videoRef.current.src = url; videoRef.current.play().catch(() => {}); }
    setCamActive(true);
  }, []);

  const stopCam = useCallback(() => {
    streamRef.current?.getTracks().forEach(t => t.stop());
    if (videoRef.current) { videoRef.current.srcObject = null; videoRef.current.src = ''; }
    setCamActive(false);
  }, []);

  // ── Calibration animation ────────────────────────────────────────
  const runCalibration = useCallback(async () => {
    setCalibrating(true);
    setCalibPct(0);
    let p = 0;
    const iv = setInterval(() => {
      p += 3 + Math.random() * 4;
      if (p >= 100) { p = 100; clearInterval(iv); setTimeout(() => setCalibrating(false), 800); }
      setCalibPct(Math.min(p, 100));
    }, 80);
    await triggerCalibration();
  }, [triggerCalibration]);

  // ── Stats derived ────────────────────────────────────────────────
  const topShot = Object.entries(stats.byType).sort((a, b) => b[1] - a[1])[0];
  const shotsPerMin = elapsed > 0 ? ((stats.total / elapsed) * 60).toFixed(1) : '—';

  return (
    <>
      <style>{css}</style>
      <div className="onyx-root">

        {/* ── Top bar ── */}
        <div className="onyx-topbar">
          <div className="onyx-logo">ONYX<span> / Live</span></div>
          <div className="onyx-status-row">
            {sessionId && (
              <span style={{ fontFamily: 'DM Mono, monospace', fontSize: 9, color: '#555c6e' }}>
                {sessionId.slice(0, 8)}…
              </span>
            )}
            <Pill
              status={status}
              label={{ idle: 'Idle', creating: 'Connecting…', connected: 'Live', error: 'Error', stopped: 'Stopped' }[status]}
            />
            <Pill status={camActive ? 'connected' : 'idle'} label={camActive ? 'Cam Live' : 'No Camera'} />
            {syncOffset && (
              <div className="onyx-sync-badge">
                RTT {Math.round(syncOffset.rtt_ms)}ms · Δ{Math.round(syncOffset.offset_ms)}ms
              </div>
            )}
            <div className="onyx-timer">{timerStr}</div>
          </div>
        </div>

        {/* ── Error banner ── */}
        {error && <div className="onyx-error-banner">⚠ {error}</div>}

        {/* ── Calibration banner ── */}
        {calibrating && (
          <div className="onyx-calib-banner">
            <span>Syncing clocks…</span>
            <div className="onyx-calib-bar">
              <div className="onyx-calib-fill" style={{ width: `${calibPct}%` }} />
            </div>
            <span style={{ minWidth: 32 }}>{Math.round(calibPct)}%</span>
          </div>
        )}

        {/* ── Main grid ── */}
        <div className="onyx-grid">

          {/* LEFT */}
          <div className="onyx-left">

            {/* Camera box */}
            <div className="onyx-cam">
              <video ref={videoRef} autoPlay muted playsInline />
              {!camActive && (
                <div className="onyx-cam-overlay">
                  <div className="onyx-cam-hint">No video source</div>
                  <div className="onyx-cam-btns">
                    <button className="onyx-btn onyx-btn-primary" onClick={startWebcam}>Use Webcam</button>
                    <button className="onyx-btn onyx-btn-blue" onClick={() => setShowIpInput(v => !v)}>IP Camera</button>
                  </div>
                  {showIpInput && (
                    <div className="onyx-ip-row">
                      <input id="onyx-ip-input" placeholder="http://192.168.x.x:81/stream" />
                      <button className="onyx-btn onyx-btn-blue" onClick={connectIpCam}>Go</button>
                    </div>
                  )}
                </div>
              )}
              {camActive && (
                <button
                  className="onyx-btn onyx-btn-danger"
                  style={{ position: 'absolute', top: 8, right: 8, padding: '4px 10px', fontSize: 10 }}
                  onClick={stopCam}
                >
                  Stop Cam
                </button>
              )}
              {/* Shot flash overlay */}
              {flashShot && (() => {
                const m = SHOT_META[flashShot.type] ?? { color: '#fff', bg: 'rgba(255,255,255,0.1)' };
                return (
                  <div className="onyx-shot-flash" style={{ background: m.bg, borderColor: m.color, color: m.color, opacity: 1 }}>
                    {flashShot.type} · {Math.round(flashShot.confidence * 100)}%
                  </div>
                );
              })()}
            </div>

            {/* Metric cards */}
            <div className="onyx-metrics">
              <div className="onyx-metric">
                <div className="onyx-metric-label">Total Shots</div>
                <div className="onyx-metric-value" style={{ color: '#00e5a0' }}>{stats.total}</div>
                <div className="onyx-metric-sub">{shotsPerMin} / min</div>
              </div>
              <div className="onyx-metric">
                <div className="onyx-metric-label">Top Shot</div>
                <div className="onyx-metric-value" style={{ fontSize: 15, paddingTop: 4, color: SHOT_META[topShot?.[0]]?.color ?? '#555c6e' }}>
                  {topShot?.[1] > 0 ? topShot[0] : '—'}
                </div>
                <div className="onyx-metric-sub">
                  {topShot?.[1] > 0 ? `${Math.round(topShot[1] / stats.total * 100)}% of shots` : 'no data'}
                </div>
              </div>
              <div className="onyx-metric">
                <div className="onyx-metric-label">Avg Confidence</div>
                <div className="onyx-metric-value" style={{ color: '#ffb347' }}>
                  {stats.total > 0 ? `${Math.round(stats.avgConfidence * 100)}%` : '—'}
                </div>
                <div className="onyx-metric-sub">IMU classifier</div>
              </div>
              <div className="onyx-metric">
                <div className="onyx-metric-label">Session</div>
                <div className="onyx-metric-value" style={{ fontSize: 14, paddingTop: 4, color: { idle:'#555c6e', creating:'#00e5a0', connected:'#00e5a0', error:'#ff5c5c', stopped:'#ffb347' }[status] }}>
                  {{ idle:'Idle', creating:'Starting…', connected:'Active', error:'Error', stopped:'Stopped' }[status]}
                </div>
                <div className="onyx-metric-sub">{sessionId ? `ID: ${sessionId.slice(0, 8)}` : 'no session'}</div>
              </div>
            </div>

            {/* Controls */}
            <div className="onyx-ctrl-row">
              {(status === 'idle' || status === 'stopped' || status === 'error') && (
                <button className="onyx-btn onyx-btn-primary" onClick={() => startSession(30)}>Start Session</button>
              )}
              {status === 'connected' && (
                <button className="onyx-btn onyx-btn-danger" onClick={stopSession}>Stop Session</button>
              )}
              <button
                className="onyx-btn onyx-btn-warn"
                disabled={status !== 'connected' || !syncOffset}
                onClick={runCalibration}
              >
                Calibrate Clocks
              </button>
              <button className="onyx-btn onyx-btn-ghost" onClick={reset}>Reset</button>
            </div>
          </div>

          {/* RIGHT */}
          <div className="onyx-right">

            {/* Shot timeline */}
            <div className="onyx-panel">
              <div className="onyx-panel-header">
                <span>Shot Timeline</span>
                <span className="onyx-panel-header-ts">
                  {stats.lastShot ? fmtTime(stats.lastShot.timestamp) : '—'}
                </span>
              </div>
              <div className="onyx-timeline">
                {shots.length === 0
                  ? <div className="onyx-empty">Waiting for sensor events from ESP32…</div>
                  : shots.map((s, i) => {
                    const m = SHOT_META[s.type] ?? { color: '#fff', bg: 'rgba(255,255,255,0.1)' };
                    return (
                      <div className="onyx-shot-row" key={s.id ?? i}>
                        <span className="onyx-type-badge" style={{ background: m.bg, borderColor: m.color, color: m.color }}>
                          {s.type}
                        </span>
                        <div className="onyx-conf-bar">
                          <div className="onyx-conf-fill" style={{ width: `${Math.round(s.confidence * 100)}%`, background: m.color }} />
                        </div>
                        <span style={{ fontFamily: 'DM Mono, monospace', fontSize: 10, color: '#555c6e' }}>
                          {Math.round(s.confidence * 100)}%
                        </span>
                        <span className="onyx-shot-meta">{fmtTime(s.timestamp)}</span>
                      </div>
                    );
                  })
                }
              </div>
            </div>

            {/* Charts */}
            <div className="onyx-chart-row">
              <div className="onyx-panel">
                <div className="onyx-panel-header"><span>Shot Distribution</span></div>
                <DistributionChart byType={stats.byType} />
              </div>
              <div className="onyx-panel">
                <div className="onyx-panel-header"><span>Rate / 10s</span></div>
                <RateChart rateHistory={stats.rateHistory} />
              </div>
            </div>

            <div className="onyx-panel">
              <div className="onyx-panel-header"><span>Classifier Confidence Stream</span></div>
              <ConfidenceChart shots={shots} />
            </div>

          </div>
        </div>
      </div>
    </>
  );
}
