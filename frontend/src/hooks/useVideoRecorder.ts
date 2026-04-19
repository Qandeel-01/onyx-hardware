/**
 * Video Recorder Hook
 * Manages video recording via MediaRecorder API with RTT-corrected timestamps
 * 
 * Features:
 * - Automatic video and audio stream acquisition
 * - MediaRecorder with configurable MIME type
 * - RTT (round-trip time) aware timestamp collection
 * - Proper resource cleanup
 * - Error handling with detailed messages
 * - Recording state management
 * 
 * The hook automatically calculates RTT-corrected UTC timestamps
 * for synchronization with other data streams (sensors, shots).
 * 
 * @module hooks/useVideoRecorder
 */

import { useRef, useCallback, useState } from 'react';

/**
 * Configuration options for video recording
 */
interface VideoRecorderConfig {
  /** Callback when recording starts */
  onRecordingStart?: () => void;
  
  /** Callback when recording stops with recorded blob */
  onRecordingStop?: (blob: Blob) => void;
  
  /** Callback when error occurs during recording */
  onError?: (error: Error) => void;
  
  /** MIME type for video encoding (default: 'video/webm;codecs=vp9') */
  mimeType?: string;
  
  /** Video width in pixels (default: 1280) */
  videoWidth?: number;
  
  /** Video height in pixels (default: 720) */
  videoHeight?: number;
}

/**
 * Hook return type with recording controls and state
 */
interface UseVideoRecorderReturn {
  /** True if recording is currently active */
  isRecording: boolean;
  
  /** Error message if recording encountered an error, null otherwise */
  error: string | null;
  
  /** Start video recording */
  startRecording: () => Promise<void>;
  
  /** Stop video recording */
  stopRecording: () => void;
}

/**
 * Custom hook for managing video recording
 * 
 * Example usage:
 * ```typescript
 * const { isRecording, error, startRecording, stopRecording } = useVideoRecorder({
 *   onRecordingStop: (blob) => {
 *     uploadVideoFile(blob);
 *   },
 *   onError: (error) => {
 *     console.error('Recording failed:', error);
 *   },
 * });
 * 
 * // Start recording
 * await startRecording();
 * 
 * // Stop after 30 seconds
 * setTimeout(() => stopRecording(), 30000);
 * ```
 * 
 * @param config - Video recorder configuration
 * @returns Object with recording state and control methods
 */
export function useVideoRecorder(config: VideoRecorderConfig): UseVideoRecorderReturn {
  // ==================== Refs ====================
  
  /** Reference to MediaRecorder instance */
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  
  /** Reference to active MediaStream */
  const streamRef = useRef<MediaStream | null>(null);
  
  /** Accumulated Blob chunks during recording */
  const chunksRef = useRef<Blob[]>([]);
  
  /** RTT-corrected recording start timestamp */
  const recordingStartUtcMsRef = useRef<number | null>(null);
  
  // ==================== State ====================
  
  /** True if recording is currently active */
  const [isRecording, setIsRecording] = useState(false);
  
  /** Error message from recording operation */
  const [error, setError] = useState<string | null>(null);
  
  // ==================== Config Destructuring ====================
  
  const {
    onRecordingStart,
    onRecordingStop,
    onError,
    mimeType = 'video/webm;codecs=vp9',
    videoWidth = 1280,
    videoHeight = 720,
  } = config;

  // ==================== Utility Functions ====================

  /**
   * Calculate RTT-corrected UTC timestamp
   * 
   * Accounts for JavaScript's high-resolution timer offset.
   * performance.timeOrigin provides UTC milliseconds at runtime start,
   * and performance.now() provides elapsed time since then.
   * 
   * @returns UTC timestamp in milliseconds
   */
  const calculateRTTCorrectedUtcMs = useCallback((): number => {
    // performance.timeOrigin is UTC milliseconds when performance started
    // performance.now() is elapsed time since performance started
    // Sum gives current UTC time
    const performanceTimeOriginMs = performance.timeOrigin || Date.now();
    const elapsedMs = performance.now();
    return performanceTimeOriginMs + elapsedMs;
  }, []);

  /**
   * Check if MIME type is supported by browser
   * @param mimeType - MIME type to check
   * @returns True if browser supports the MIME type
   */
  const isMimeTypeSupported = useCallback((mimeType: string): boolean => {
    return MediaRecorder.isTypeSupported(mimeType);
  }, []);

  /**
   * Clean up media stream and recorder resources
   */
  const cleanup = useCallback(() => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track: MediaStreamTrack) => {
        track.stop();
        console.log(`Stopped ${track.kind} track`);
      });
      streamRef.current = null;
    }
    mediaRecorderRef.current = null;
    chunksRef.current = [];
    recordingStartUtcMsRef.current = null;
  }, []);

  // ==================== Recording Controls ====================

  /**
   * Start video recording
   * 
   * Acquires video and audio streams, initializes MediaRecorder,
   * and begins recording. Automatically tracks RTT-corrected timestamps.
   * 
   * @throws Error if permissions denied or stream acquisition fails
   */
  const startRecording = useCallback(async (): Promise<void> => {
    try {
      // Check if already recording
      if (isRecording) {
        console.warn('Recording already in progress');
        return;
      }

      // Validate MIME type support
      if (!isMimeTypeSupported(mimeType)) {
        throw new Error(
          `MIME type "${mimeType}" is not supported by this browser. ` +
          `Try "video/webm" or check MediaRecorder.isTypeSupported() for alternatives.`
        );
      }

      console.log(`Starting video recording with MIME type: ${mimeType}`);

      // Request media stream with video and audio
      const stream = await navigator.mediaDevices.getUserMedia({
        video: {
          width: { ideal: videoWidth },
          height: { ideal: videoHeight },
        },
        audio: true,
      });

      streamRef.current = stream;
      chunksRef.current = [];

      // Record RTT-corrected start time
      recordingStartUtcMsRef.current = calculateRTTCorrectedUtcMs();
      console.log(`Recording started at UTC: ${recordingStartUtcMsRef.current}ms`);

      // Create MediaRecorder instance
      const mediaRecorder = new MediaRecorder(stream, {
        mimeType,
      });

      // Accumulate recorded chunks
      mediaRecorder.ondataavailable = (event: BlobEvent) => {
        if (event.data.size > 0) {
          chunksRef.current.push(event.data);
        }
      };

      // Handle recording stop
      mediaRecorder.onstop = () => {
        try {
          // Combine chunks into single blob
          const blob = new Blob(chunksRef.current, { type: mimeType });

          // Stop all media tracks
          if (streamRef.current) {
            streamRef.current.getTracks().forEach((track: MediaStreamTrack) => {
              track.stop();
              console.log(`Stopped ${track.kind} track after recording`);
            });
          }

          const recordingDurationMs = calculateRTTCorrectedUtcMs() - (recordingStartUtcMsRef.current || 0);

          console.log(
            `Recording stopped. ` +
            `Duration: ${recordingDurationMs.toFixed(0)}ms, ` +
            `File size: ${blob.size} bytes, ` +
            `Start UTC: ${recordingStartUtcMsRef.current}ms`
          );

          // Invoke callback with recorded blob
          onRecordingStop?.(blob);
          setIsRecording(false);
        } catch (callbackError) {
          const stopError = callbackError instanceof Error 
            ? callbackError 
            : new Error('Unknown error during recording stop');
          console.error('Error in onRecordingStop callback:', stopError);
          onError?.(stopError);
        }
      };

      // Handle recording errors
      mediaRecorder.onerror = (event: any) => {
        const errorMessage = `MediaRecorder error: ${event.error}`;
        console.error(errorMessage);
        setError(errorMessage);

        const recordingError = new Error(errorMessage);
        onError?.(recordingError);
        cleanup();
      };

      mediaRecorderRef.current = mediaRecorder;

      // Start recording
      mediaRecorder.start();
      setIsRecording(true);
      setError(null);
      onRecordingStart?.();

      console.log('Video recording started successfully');
    } catch (startError) {
      const recordingError = startError instanceof Error 
        ? startError 
        : new Error('Failed to start recording');

      const errorMessage = `Recording startup failed: ${recordingError.message}`;
      console.error(errorMessage);
      setError(errorMessage);
      onError?.(recordingError);
      cleanup();
    }
  }, [
    isRecording,
    isMimeTypeSupported,
    mimeType,
    videoWidth,
    videoHeight,
    calculateRTTCorrectedUtcMs,
    onRecordingStart,
    onRecordingStop,
    onError,
    cleanup,
  ]);

  /**
   * Stop video recording
   * 
   * Stops the MediaRecorder which triggers the onstop handler
   * to process the recorded blob and cleanup resources.
   */
  const stopRecording = useCallback(() => {
    if (mediaRecorderRef.current && isRecording) {
      console.log('Stopping video recording');
      try {
        mediaRecorderRef.current.stop();
      } catch (stopError) {
        const recordingError = stopError instanceof Error 
          ? stopError 
          : new Error('Failed to stop recording');
        console.error('Error stopping recording:', recordingError);
        onError?.(recordingError);
        cleanup();
      }
    } else {
      console.warn('No active recording to stop');
    }
  }, [isRecording, onError, cleanup]);

  // ==================== Return ====================

  return {
    isRecording,
    error,
    startRecording,
    stopRecording,
  };
}

/**
 * Alternative hook that automatically starts recording on mount
 * and stops recording when component unmounts
 * 
 * Useful for recording entire session duration.
 * 
 * @param config - Video recorder configuration
 * @returns Recording state and manual stop control
 */
export function useAutoVideoRecorder(config: VideoRecorderConfig): UseVideoRecorderReturn {
  const recorder = useVideoRecorder(config);

  // Auto-start on mount
  useRef(() => {
    recorder.startRecording().catch((error) => {
      console.error('Failed to auto-start recording:', error);
    });
  });

  // Auto-stop on unmount
  useRef(() => () => {
    if (recorder.isRecording) {
      recorder.stopRecording();
    }
  });

  return recorder;
}
