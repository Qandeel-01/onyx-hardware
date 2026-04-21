/**
 * Live webcam via getUserMedia; optional MediaRecorder for local WebM download.
 */
import { useCallback, useEffect, useRef, useState } from 'react';

export type WebcamStatus = 'idle' | 'active' | 'error';

export interface UseWebcamStreamResult {
  status: WebcamStatus;
  errorMessage: string | null;
  startWebcam: () => Promise<void>;
  stopWebcam: () => void;
  attachToVideo: (el: HTMLVideoElement | null) => void;
  isRecording: boolean;
  startRecording: () => void;
  stopRecording: () => void;
}

export function useWebcamStream(): UseWebcamStreamResult {
  const streamRef = useRef<MediaStream | null>(null);
  const videoElRef = useRef<HTMLVideoElement | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  const [status, setStatus] = useState<WebcamStatus>('idle');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isRecording, setIsRecording] = useState(false);

  const attachToVideo = useCallback((el: HTMLVideoElement | null) => {
    videoElRef.current = el;
    if (el && streamRef.current) {
      el.srcObject = streamRef.current;
    }
  }, []);

  const stopWebcam = useCallback(() => {
    if (recorderRef.current && recorderRef.current.state !== 'inactive') {
      recorderRef.current.stop();
    }
    recorderRef.current = null;
    chunksRef.current = [];
    setIsRecording(false);

    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    if (videoElRef.current) {
      videoElRef.current.srcObject = null;
    }
    setStatus('idle');
  }, []);

  const startWebcam = useCallback(async () => {
    setErrorMessage(null);
    if (!navigator.mediaDevices?.getUserMedia) {
      setStatus('error');
      setErrorMessage('Camera not supported in this browser.');
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: {
          facingMode: 'user',
          width: { ideal: 1280 },
          height: { ideal: 720 },
        },
        audio: false,
      });
      streamRef.current = stream;
      if (videoElRef.current) {
        videoElRef.current.srcObject = stream;
        await videoElRef.current.play().catch(() => undefined);
      }
      setStatus('active');
    } catch (e) {
      setStatus('error');
      setErrorMessage(
        e instanceof Error ? e.message : 'Could not access the camera.'
      );
    }
  }, []);

  const startRecording = useCallback(() => {
    const stream = streamRef.current;
    if (!stream || isRecording) return;

    const mime =
      typeof MediaRecorder !== 'undefined' &&
      MediaRecorder.isTypeSupported('video/webm;codecs=vp9')
        ? 'video/webm;codecs=vp9'
        : 'video/webm';

    chunksRef.current = [];
    try {
      const rec = new MediaRecorder(stream, { mimeType: mime });
      rec.ondataavailable = (ev) => {
        if (ev.data.size > 0) chunksRef.current.push(ev.data);
      };
      rec.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: 'video/webm' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `onyx-capture-${Date.now()}.webm`;
        a.click();
        URL.revokeObjectURL(url);
        chunksRef.current = [];
      };
      rec.start(200);
      recorderRef.current = rec;
      setIsRecording(true);
    } catch {
      setErrorMessage('Recording failed (MediaRecorder).');
    }
  }, [isRecording]);

  const stopRecording = useCallback(() => {
    if (recorderRef.current && recorderRef.current.state !== 'inactive') {
      recorderRef.current.stop();
    }
    recorderRef.current = null;
    setIsRecording(false);
  }, []);

  useEffect(() => {
    return () => {
      stopWebcam();
    };
  }, [stopWebcam]);

  return {
    status,
    errorMessage,
    startWebcam,
    stopWebcam,
    attachToVideo,
    isRecording,
    startRecording,
    stopRecording,
  };
}
