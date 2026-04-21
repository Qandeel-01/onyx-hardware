/**
 * LiveAnalysisDashboard - Main dashboard component
 */
import React, { useState, useEffect, useCallback, useRef } from 'react';
import { Session, ShotEvent, ShotStats as ShotStatsType } from '@/types';
import { useShotWebSocket } from '@/hooks/useShotWebSocket';
import { apiClient } from '@/services/apiClient';
import { CameraPanel } from './CameraPanel';
import { ShotTimeline } from './ShotTimeline';
import { ShotStats } from './ShotStats';
import { ShotDistributionChart } from '@/components/charts/ShotDistributionChart';
import { ShotRateChart } from '@/components/charts/ShotRateChart';
import { IMUIntensityChart } from '@/components/charts/IMUIntensityChart';

interface LiveAnalysisDashboardProps {
  sessionId: string;
}

export const LiveAnalysisDashboard: React.FC<LiveAnalysisDashboardProps> = ({
  sessionId,
}) => {
  const [session, setSession] = useState<Session | null>(null);
  const [shots, setShots] = useState<ShotEvent[]>([]);
  const [stats, setStats] = useState<ShotStatsType | null>(null);
  const [isLive, setIsLive] = useState(true);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Fetch session data
  useEffect(() => {
    const fetchSession = async () => {
      try {
        const data = await apiClient.getSession(sessionId);
        setSession(data);
      } catch (err) {
        setError(`Failed to fetch session: ${err}`);
      } finally {
        setLoading(false);
      }
    };

    fetchSession();
  }, [sessionId]);

  const refreshShotsAndStats = useCallback(async () => {
    try {
      const [shotsData, statsData] = await Promise.all([
        apiClient.getShotEvents(sessionId, 0, 100),
        apiClient.getShotStats(sessionId),
      ]);
      setShots(shotsData);
      setStats(statsData);
    } catch (err) {
      setError(`Failed to fetch data: ${err}`);
    }
  }, [sessionId]);

  const refreshShotsAndStatsRef = useRef(refreshShotsAndStats);
  refreshShotsAndStatsRef.current = refreshShotsAndStats;

  const [clockSync, setClockSync] = useState<{ offsetMs: number; rttMs: number } | null>(null);

  const { connected, calibrated, offsetMs, rttMs, wsEnabled } = useShotWebSocket({
    sessionId,
    onShotReceived: (shot) => {
      setShots((prev) => [shot, ...prev]);
      void refreshShotsAndStatsRef.current();
    },
    onError: (errorMsg) => {
      setError(errorMsg);
    },
    onCalibrated: (offset, rtt) => {
      // Real SYNC_PONG from ws_shots.py — update display and persist to DB.
      setClockSync({ offsetMs: offset, rttMs: rtt });
      void apiClient.recordCalibration(sessionId, rtt, offset).catch(() => {});
    },
  });

  // Fetch initial shots and stats
  useEffect(() => {
    if (!session) return;

    refreshShotsAndStats();
  }, [session, sessionId, refreshShotsAndStats]);

  // Polling when WebSocket is off or disconnected (e.g. mock backend).
  useEffect(() => {
    if (!session) return;
    if (wsEnabled && connected) return;
    const id = window.setInterval(() => {
      refreshShotsAndStats();
    }, 2000);
    return () => window.clearInterval(id);
  }, [session, refreshShotsAndStats, wsEnabled, connected]);

  const handleGenerateShot = useCallback(async () => {
    try {
      await apiClient.createShotEvent(sessionId);
      await refreshShotsAndStats();
    } catch (err) {
      setError(`Failed to simulate shot: ${err}`);
    }
  }, [sessionId, refreshShotsAndStats]);

  const handleEndSession = async () => {
    try {
      await apiClient.updateSession(sessionId, {
        ended_at: new Date().toISOString(),
      });
      setIsLive(false);
    } catch (err) {
      setError(`Failed to end session: ${err}`);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen bg-primary">
        <div className="text-center">
          <div className="mb-4 text-2xl">⏳</div>
          <p className="text-gray-400">Loading session data...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 bg-primary min-h-screen">
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-accent">Live Analysis</h1>
            <p className="text-gray-400 mt-1">
              {session?.started_at
                ? new Date(session.started_at).toLocaleString()
                : 'No date'}
            </p>
          </div>
          <div className="flex items-center gap-4">
            <div className="text-center">
              <div className="text-sm text-gray-400">Connection</div>
              <div
                className={`text-lg font-bold ${
                  wsEnabled
                    ? connected
                      ? 'text-green-400'
                      : 'text-red-400'
                    : 'text-gray-400'
                }`}
              >
                {wsEnabled
                  ? connected
                    ? '🟢 Connected'
                    : '🔴 Disconnected'
                  : '⚪ Disabled'}
              </div>
            </div>
            {(calibrated || clockSync) && (
              <div className="text-center">
                <div className="text-sm text-gray-400">Clock Sync</div>
                <div className="text-lg font-bold text-cyan-400">
                  {clockSync?.offsetMs ?? offsetMs}ms ±{' '}
                  {clockSync?.rttMs ?? rttMs}ms
                </div>
              </div>
            )}

            <div className="flex items-center gap-2">
              <button
                onClick={handleGenerateShot}
                className="px-3 py-2 bg-secondary hover:bg-gray-700 text-white rounded-lg transition-colors"
                title="Manually inject a test shot event via REST"
              >
                + Shot
              </button>
            </div>
            {isLive && (
              <button
                onClick={handleEndSession}
                className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg transition-colors"
              >
                End Session
              </button>
            )}
          </div>
        </div>

        {error && (
          <div className="p-4 bg-red-900/20 border border-red-500 rounded-lg text-red-400">
            {error}
          </div>
        )}

        {/* Camera Panel */}
        <CameraPanel session={session} isLive={isLive} />

        {/* Stats Cards */}
        <ShotStats stats={stats} />

        {/* Charts Row */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="container-primary">
            <h2 className="text-lg font-bold text-accent mb-4">
              Shot Distribution
            </h2>
            <ShotDistributionChart data={stats?.distribution || []} />
          </div>
          <div className="container-primary">
            <h2 className="text-lg font-bold text-accent mb-4">
              Shot Rate Over Time
            </h2>
            <ShotRateChart shots={shots} />
          </div>
        </div>

        {/* IMU Chart */}
        <div className="container-primary">
          <h2 className="text-lg font-bold text-accent mb-4">
            IMU Intensity (Last 20 Shots)
          </h2>
          <IMUIntensityChart shots={shots} />
        </div>

        {/* Timeline */}
        <ShotTimeline shots={shots} maxHeight="h-96" />
      </div>
    </div>
  );
};
