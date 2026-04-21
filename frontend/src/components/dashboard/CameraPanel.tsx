/**
 * CameraPanel — recorded file URL, or live webcam via getUserMedia
 */
import React, { useRef, useEffect } from 'react';
import { Session } from '@/types';
import { useWebcamStream } from '@/hooks/useWebcamStream';

interface CameraPanelProps {
  session: Session | null;
  isLive: boolean;
}

export const CameraPanel: React.FC<CameraPanelProps> = ({
  session,
  isLive,
}) => {
  const videoRef = useRef<HTMLVideoElement>(null);
  const {
    status: webcamStatus,
    errorMessage: webcamError,
    startWebcam,
    stopWebcam,
    attachToVideo,
    isRecording,
    startRecording,
    stopRecording,
  } = useWebcamStream();

  useEffect(() => {
    attachToVideo(videoRef.current);
  }, [attachToVideo, webcamStatus]);

  useEffect(() => {
    if (!isLive || !session?.video_file_path || !videoRef.current) return;
    if (webcamStatus === 'active') return;

    const video = videoRef.current;
    video.srcObject = null;
    video.src = session.video_file_path;
    video.play().catch((err) => console.error('Failed to play video:', err));
  }, [session?.video_file_path, isLive, webcamStatus]);

  const showFile =
    session?.video_file_path &&
    isLive &&
    webcamStatus !== 'active';

  return (
    <div className="container-primary h-96 flex flex-col">
      <div className="mb-4 flex items-center justify-between flex-wrap gap-2">
        <h2 className="text-xl font-bold text-accent">
          {isLive ? 'Live Feed' : 'Recorded Session'}
        </h2>
        <div className="flex items-center gap-2 flex-wrap">
          {isLive && (
            <>
              {webcamStatus !== 'active' ? (
                <button
                  type="button"
                  onClick={() => void startWebcam()}
                  className="px-3 py-1.5 bg-cyan-700 hover:bg-cyan-600 text-white text-sm rounded-lg"
                >
                  Use webcam
                </button>
              ) : (
                <>
                  <div className="flex items-center gap-2">
                    <div className="w-3 h-3 bg-red-500 rounded-full animate-pulse" />
                    <span className="text-sm text-gray-400">Webcam</span>
                  </div>
                  {!isRecording ? (
                    <button
                      type="button"
                      onClick={startRecording}
                      className="px-3 py-1.5 bg-violet-700 hover:bg-violet-600 text-white text-sm rounded-lg"
                    >
                      Record clip
                    </button>
                  ) : (
                    <button
                      type="button"
                      onClick={stopRecording}
                      className="px-3 py-1.5 bg-amber-700 hover:bg-amber-600 text-white text-sm rounded-lg"
                    >
                      Stop &amp; download
                    </button>
                  )}
                  <button
                    type="button"
                    onClick={stopWebcam}
                    className="px-3 py-1.5 bg-secondary hover:bg-gray-600 text-white text-sm rounded-lg"
                  >
                    Stop webcam
                  </button>
                </>
              )}
            </>
          )}
        </div>
      </div>

      {webcamError && (
        <p className="text-sm text-red-400 mb-2">{webcamError}</p>
      )}

      <div className="flex-1 bg-black rounded-lg overflow-hidden border border-secondary flex items-center justify-center">
        {showFile ? (
          <video
            ref={videoRef}
            className="w-full h-full object-contain"
            controls
          />
        ) : webcamStatus === 'active' ? (
          <video
            ref={videoRef}
            className="w-full h-full object-contain"
            autoPlay
            playsInline
            muted
          />
        ) : (
          <div className="flex flex-col items-center gap-2 text-gray-400 px-4 text-center">
            <p>
              {session
                ? 'Use webcam or provide a session video URL from the API'
                : 'Start a session to view camera feed'}
            </p>
          </div>
        )}
      </div>

      {session && (
        <div className="mt-4 grid grid-cols-3 gap-4 text-sm">
          <div>
            <span className="text-gray-400">FPS:</span>
            <p className="font-mono text-accent">{session.fps || '—'}</p>
          </div>
          <div>
            <span className="text-gray-400">Quality:</span>
            <p className="font-mono text-accent">
              {session.sync_quality || '—'}
            </p>
          </div>
          <div>
            <span className="text-gray-400">Duration:</span>
            <p className="font-mono text-accent">
              {session.ended_at
                ? Math.round(
                    (new Date(session.ended_at).getTime() -
                      new Date(session.started_at).getTime()) /
                      1000
                  ) + 's'
                : '—'}
            </p>
          </div>
        </div>
      )}
    </div>
  );
};
