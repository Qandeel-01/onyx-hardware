/**
 * Session Store - Zustand + Immer + Persist
 * Global state management for ONYX session data
 * 
 * This store manages:
 * - Current recording session metadata
 * - Shot detections and fused results
 * - Device status and battery metrics
 * - Clock synchronization state
 * - Multi-step calibration progress
 * - WebSocket connection state
 * 
 * Automatically persists to sessionStorage for recovery across page reloads.
 * Uses Immer for immutable state mutations with convenient mutative syntax.
 * 
 * @module store/sessionStore
 */

import { create } from 'zustand';
import { immer } from 'zustand/middleware/immer';
import { persist } from 'zustand/middleware';
import {
  Session,
  FusedShot,
  DeviceStatus,
  ClockSyncState,
  ClockSyncSample,
  CalibrationState,
  CourtCorner,
} from '../types/onyx';

/**
 * Complete session store state interface
 * All state and action methods with strict typing
 */
interface SessionStore {
  // ==================== State ====================
  
  /** Current active recording session or null if no session */
  session: Session | null;
  
  /** Array of detected shots in current session */
  shots: FusedShot[];
  
  /** Latest device status update */
  deviceStatus: DeviceStatus | null;
  
  /** Clock synchronization state with offset calculations */
  clockSync: ClockSyncState;
  
  /** Multi-step calibration progress and results */
  calibration: CalibrationState;
  
  /** True if WebSocket connection is active */
  wsConnected: boolean;
  
  // ==================== Actions ====================
  
  /**
   * Set the active session
   * @param session - Session to set as active
   */
  setSession: (session: Session) => void;
  
  /**
   * Add a new shot to the shots array
   * @param shot - FusedShot to add
   */
  addShot: (shot: FusedShot) => void;
  
  /**
   * Clear all shots from current session
   */
  clearShots: () => void;
  
  /**
   * Update the latest device status
   * @param status - DeviceStatus with current device metrics
   */
  setDeviceStatus: (status: DeviceStatus) => void;
  
  /**
   * Add a clock synchronization sample
   * Appends to samples array and enables sync state
   * @param sample - ClockSyncSample from SNTP handshake
   */
  addClockSyncSample: (sample: ClockSyncSample) => void;
  
  /**
   * Clear all clock sync samples
   */
  clearClockSyncSamples: () => void;
  
  /**
   * Update calculated clock offset
   * @param offset_ms - Calculated offset in milliseconds
   * @param quality - Quality assessment of synchronization
   */
  setClockSyncOffset: (offset_ms: number, quality: CalibrationState['quality']) => void;
  
  /**
   * Update completion state of a calibration step
   * @param step - Step identifier
   * @param completed - Completion status
   * @param error - Optional error message if step failed
   */
  setCalibrationStep: (step: string, completed: boolean, error?: string | null) => void;
  
  /**
   * Set court corner calibration points
   * @param corners - Array of four CourtCorner points
   */
  setCourtCorners: (corners: CourtCorner[]) => void;
  
  /**
   * Set flash (latency) calibration results
   * Marks verify step as complete and updates offset
   * @param offset_ms - Calculated latency offset in milliseconds
   * @param quality - Quality assessment of calibration
   */
  setFlashCalibration: (offset_ms: number, quality: string) => void;
  
  /**
   * Update WebSocket connection state
   * @param connected - True if connection is active
   */
  setWsConnected: (connected: boolean) => void;
  
  /**
   * Reset store to initial state
   * Clears session, shots, and calibration data
   */
  reset: () => void;
}

/**
 * Initial store state
 * Defines defaults for all state properties
 */
const initialState: Omit<SessionStore, keyof {
  setSession: any;
  addShot: any;
  clearShots: any;
  setDeviceStatus: any;
  addClockSyncSample: any;
  clearClockSyncSamples: any;
  setClockSyncOffset: any;
  setCalibrationStep: any;
  setCourtCorners: any;
  setFlashCalibration: any;
  setWsConnected: any;
  reset: any;
}> = {
  session: null,
  shots: [],
  deviceStatus: null,
  clockSync: {
    samples: [],
    offset_ms: null,
    quality: 'unknown',
    is_syncing: false,
  },
  calibration: {
    steps: {
      corner_picker: { step: 'corner_picker', completed: false, error: null },
      flash_setup: { step: 'flash_setup', completed: false, error: null },
      flash_record: { step: 'flash_record', completed: false, error: null },
      verify: { step: 'verify', completed: false, error: null },
    },
    court_corners: [],
    flash_residual_offset_ms: null,
    quality: 'unknown',
  },
  wsConnected: false,
};

/**
 * Custom persistence storage for sessionStorage
 * Provides localStorage interface for Zustand persist middleware
 */
const createSessionStorageStorage = () => ({
  getItem: (name: string) => {
    try {
      if (typeof window === 'undefined') return null;
      const item = window.sessionStorage.getItem(name);
      return item ? JSON.parse(item) : null;
    } catch (error) {
      console.error(`Failed to get item from sessionStorage: ${name}`, error);
      return null;
    }
  },
  setItem: (name: string, value: any) => {
    try {
      if (typeof window === 'undefined') return;
      window.sessionStorage.setItem(name, JSON.stringify(value));
    } catch (error) {
      console.error(`Failed to set item in sessionStorage: ${name}`, error);
    }
  },
  removeItem: (name: string) => {
    try {
      if (typeof window === 'undefined') return;
      window.sessionStorage.removeItem(name);
    } catch (error) {
      console.error(`Failed to remove item from sessionStorage: ${name}`, error);
    }
  },
});

/**
 * Create and export the Zustand store with Immer and Persist middleware
 * 
 * Middleware stack:
 * 1. immer - Enables convenient mutative state updates
 * 2. persist - Automatically saves/restores state to sessionStorage
 */
export const useSessionStore = create<SessionStore>()(
  persist(
    immer((set: any) => ({
      ...initialState,
      
      setSession: (session: Session) => set({ session }),
      
      addShot: (shot: FusedShot) => set((state: any) => {
        state.shots.push(shot);
      }),
      
      clearShots: () => set((state: any) => {
        state.shots = [];
      }),
      
      setDeviceStatus: (status: DeviceStatus) => set({ deviceStatus: status }),
      
      addClockSyncSample: (sample: ClockSyncSample) => set((state: any) => {
        state.clockSync.samples.push(sample);
        state.clockSync.is_syncing = true;
      }),
      
      clearClockSyncSamples: () => set((state: any) => {
        state.clockSync.samples = [];
        state.clockSync.is_syncing = false;
      }),
      
      setClockSyncOffset: (offset_ms: number, quality: string) => set((state: any) => {
        state.clockSync.offset_ms = offset_ms;
        state.clockSync.quality = quality;
        state.clockSync.is_syncing = false;
      }),
      
      setCalibrationStep: (step: string, completed: boolean, error?: string | null) => set((state: any) => {
        if (state.calibration.steps[step]) {
          state.calibration.steps[step].completed = completed;
          state.calibration.steps[step].error = error ?? null;
        }
      }),
      
      setCourtCorners: (corners: CourtCorner[]) => set((state: any) => {
        if (corners.length === 4) {
          state.calibration.court_corners = corners;
        } else {
          console.warn(`Expected 4 court corners, got ${corners.length}`);
        }
      }),
      
      setFlashCalibration: (offset_ms: number, quality: string) => set((state: any) => {
        state.calibration.flash_residual_offset_ms = offset_ms;
        state.calibration.quality = quality;
        if (state.calibration.steps.verify) {
          state.calibration.steps.verify.completed = true;
          state.calibration.steps.verify.error = null;
        }
      }),
      
      setWsConnected: (connected: boolean) => set({ wsConnected: connected }),
      
      reset: () => set(initialState),
    })),
    {
      name: 'onyx-session-store',
      storage: createSessionStorageStorage(),
      partialize: (state: any) => ({
        // Only persist session, shots, and calibration data
        // Exclude volatile WebSocket connection state
        session: state.session,
        shots: state.shots,
        calibration: state.calibration,
        deviceStatus: state.deviceStatus,
        clockSync: state.clockSync,
      }),
    }
  )
);

/**
 * Selector hook for getting only session metadata
 * Optimizes re-renders by not triggering on shots/status changes
 * @returns Current session or null
 */
export const useSession = () => useSessionStore((state: any) => state.session);

/**
 * Selector hook for getting current shots
 * @returns Array of FusedShot objects
 */
export const useShots = () => useSessionStore((state: any) => state.shots);

/**
 * Selector hook for device status
 * @returns Current DeviceStatus or null
 */
export const useDeviceStatus = () => useSessionStore((state: any) => state.deviceStatus);

/**
 * Selector hook for clock sync state
 * @returns ClockSyncState with samples and offset
 */
export const useClockSync = () => useSessionStore((state: any) => state.clockSync);

/**
 * Selector hook for calibration state
 * @returns CalibrationState with all steps
 */
export const useCalibration = () => useSessionStore((state: any) => state.calibration);

/**
 * Selector hook for WebSocket connection status
 * @returns True if WebSocket is connected
 */
export const useWebSocketConnected = () => useSessionStore((state: any) => state.wsConnected);
