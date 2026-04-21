/**
 * API client for backend communication
 */
import axios, { AxiosInstance } from 'axios';
import { Session, ShotEvent, ClockCalibration, ShotStats } from '@/types';

/** Matches strings Pydantic accepts as UUID (8-4-4-4-12 hex). */
const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function isValidPlayerUuid(value: string): boolean {
  return UUID_RE.test(value.trim());
}

// Vite runs in the browser; `process.env` is not available.
// Use Vite env vars (must be prefixed with `VITE_`) and fall back to the dev proxy.
const API_BASE_URL = (
  import.meta.env.VITE_API_URL ||
  import.meta.env.VITE_API_BASE_URL ||
  '/api'
).replace(/\/$/, '');

class ApiClient {
  private client: AxiosInstance;

  constructor() {
    this.client = axios.create({
      baseURL: API_BASE_URL,
      headers: {
        'Content-Type': 'application/json',
      },
    });
  }

  // Session endpoints
  async createSession(playerId?: string): Promise<Session> {
    const trimmed = playerId?.trim();
    if (trimmed && !isValidPlayerUuid(trimmed)) {
      throw new Error(
        'Player ID must be a valid UUID (e.g. from your player registry), or leave the field empty.'
      );
    }
    const body: Record<string, string> = {};
    if (trimmed) {
      body.player_id = trimmed;
    }
    const response = await this.client.post<Session>('/sessions', body);
    return response.data;
  }

  async getSession(sessionId: string): Promise<Session> {
    const response = await this.client.get<Session>(`/sessions/${sessionId}`);
    return response.data;
  }

  async updateSession(
    sessionId: string,
    updates: Partial<Session>
  ): Promise<Session> {
    const response = await this.client.patch<Session>(
      `/sessions/${sessionId}`,
      updates
    );
    return response.data;
  }

  // Shot endpoints
  async getShotEvents(
    sessionId: string,
    skip: number = 0,
    limit: number = 100
  ): Promise<ShotEvent[]> {
    const response = await this.client.get<ShotEvent[]>(
      `/sessions/${sessionId}/shots`,
      { params: { skip, limit } }
    );
    return response.data;
  }

  async createShotEvent(
    sessionId: string,
    event?: Partial<ShotEvent>
  ): Promise<ShotEvent> {
    const response = await this.client.post<ShotEvent>(
      `/sessions/${sessionId}/shots`,
      event ?? {}
    );
    return response.data;
  }

  async getShotStats(sessionId: string): Promise<ShotStats> {
    const response = await this.client.get<ShotStats>(
      `/sessions/${sessionId}/shots/stats`
    );
    return response.data;
  }

  // Calibration endpoints
  async recordCalibration(
    sessionId: string,
    rtt_ms: number,
    offset_ms: number
  ): Promise<ClockCalibration> {
    const response = await this.client.post<ClockCalibration>(
      `/sessions/${sessionId}/calibrations`,
      { rtt_ms, offset_ms }
    );
    return response.data;
  }

  async getCalibrations(sessionId: string): Promise<ClockCalibration[]> {
    const response = await this.client.get<ClockCalibration[]>(
      `/sessions/${sessionId}/calibrations`
    );
    return response.data;
  }
}

export const apiClient = new ApiClient();
