/**
 * SessionManager - Component for creating and managing sessions
 */
import React, { useState } from 'react';
import axios from 'axios';
import { Session } from '@/types';
import { apiClient } from '@/services/apiClient';

function formatSessionCreateError(err: unknown): string {
  if (axios.isAxiosError(err) && err.response?.data) {
    const data = err.response.data as { detail?: unknown };
    const { detail } = data;
    if (Array.isArray(detail)) {
      return detail
        .map((item: { msg?: string; loc?: string[] }) =>
          [item.loc?.join('.'), item.msg].filter(Boolean).join(': ')
        )
        .join('; ');
    }
    if (typeof detail === 'string') {
      return detail;
    }
  }
  if (err instanceof Error) {
    return err.message;
  }
  return String(err);
}

interface SessionManagerProps {
  onSessionCreated: (session: Session) => void;
}

export const SessionManager: React.FC<SessionManagerProps> = ({
  onSessionCreated,
}) => {
  const [loading, setLoading] = useState(false);
  const [playerId, setPlayerId] = useState('');
  const [error, setError] = useState<string | null>(null);

  const handleCreateSession = async () => {
    try {
      setLoading(true);
      setError(null);
      const session = await apiClient.createSession(playerId || undefined);
      onSessionCreated(session);
    } catch (err) {
      setError(`Failed to create session: ${formatSessionCreateError(err)}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex items-center justify-center min-h-screen bg-primary">
      <div className="container-primary max-w-md w-full">
        <h1 className="text-3xl font-bold text-accent mb-6">
          Project ONYX
        </h1>
        <p className="text-gray-400 mb-6">
          Real-time Padel Analytics with Wearable IoT
        </p>

        <p className="text-xs text-gray-500 mb-4">
          API docs:{' '}
          <a
            href="http://127.0.0.1:8000/docs"
            target="_blank"
            rel="noopener noreferrer"
            className="text-accent underline hover:text-cyan-300"
          >
            :8000/docs
          </a>
          {' · '}
          <a
            href="/docs"
            target="_blank"
            rel="noopener noreferrer"
            className="text-accent underline hover:text-cyan-300"
          >
            /docs (Vite proxy)
          </a>
        </p>

        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-2">
              Player UUID (optional)
            </label>
            <input
              type="text"
              value={playerId}
              onChange={(e) => setPlayerId(e.target.value)}
              placeholder="e.g. 550e8400-e29b-41d4-a716-446655440000 — or leave blank"
              className="w-full px-4 py-2 bg-secondary border border-gray-600 rounded-lg text-white focus:outline-none focus:border-accent"
            />
          </div>

          {error && (
            <div className="p-3 bg-red-900/20 border border-red-500 rounded-lg text-red-400 text-sm">
              {error}
            </div>
          )}

          <button
            onClick={handleCreateSession}
            disabled={loading}
            className="w-full px-4 py-3 bg-accent hover:bg-cyan-600 disabled:bg-gray-600 text-white font-semibold rounded-lg transition-colors"
          >
            {loading ? 'Creating...' : 'Start Session'}
          </button>
        </div>

        <div className="mt-8 pt-6 border-t border-secondary">
          <h3 className="text-sm font-semibold text-accent mb-3">Features</h3>
          <ul className="space-y-2 text-xs text-gray-400">
            <li>✓ Real-time shot detection via ESP32</li>
            <li>✓ Clock synchronization protocol</li>
            <li>✓ IMU sensor fusion (accel + gyro)</li>
            <li>✓ Live analytics dashboard</li>
            <li>✓ Shot statistics & trends</li>
          </ul>
        </div>
      </div>
    </div>
  );
};
