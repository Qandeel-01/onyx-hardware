/**
 * ShotTimeline - Chronological list of shot events
 */
import React from 'react';
import { ShotEvent, ShotType } from '@/types';
import { formatDistanceToNow } from 'date-fns';

interface ShotTimelineProps {
  shots: ShotEvent[];
  maxHeight?: string;
}

const SHOT_COLORS: Record<ShotType, string> = {
  [ShotType.FOREHAND]: 'bg-cyan-500',
  [ShotType.BACKHAND]: 'bg-violet-500',
  [ShotType.SMASH]: 'bg-red-500',
  [ShotType.VOLLEY]: 'bg-emerald-500',
  [ShotType.BANDEJA]: 'bg-amber-500',
  [ShotType.LOB]: 'bg-blue-500',
};

export const ShotTimeline: React.FC<ShotTimelineProps> = ({
  shots,
  maxHeight = 'h-96',
}) => {
  const sortedShots = [...shots].reverse(); // Most recent first

  if (sortedShots.length === 0) {
    return (
      <div
        className={`container-primary flex items-center justify-center text-gray-400 ${maxHeight}`}
      >
        <p>No shots recorded yet</p>
      </div>
    );
  }

  return (
    <div className={`container-primary overflow-y-auto ${maxHeight}`}>
      <h3 className="text-lg font-bold text-accent mb-4 sticky top-0 bg-primary">
        Shot Timeline
      </h3>
      <div className="space-y-2">
        {sortedShots.map((shot, index) => (
          <div
            key={shot.id}
            className={`flex items-start gap-4 p-3 rounded-lg border border-secondary card-hover ${
              index === 0 ? 'bg-secondary/50' : 'bg-transparent'
            }`}
          >
            <div
              className={`w-3 h-3 rounded-full mt-1.5 flex-shrink-0 ${
                SHOT_COLORS[shot.shot_type]
              }`}
            ></div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center justify-between gap-2">
                <span className="font-semibold text-accent">
                  {shot.shot_type}
                </span>
                <span className="text-xs text-gray-500">
                  {formatDistanceToNow(new Date(shot.created_at), {
                    addSuffix: true,
                  })}
                </span>
              </div>
              <div className="mt-1 flex items-center gap-2 text-sm">
                <span className="text-gray-400">Confidence:</span>
                <div className="flex-1 max-w-xs">
                  <div className="w-full bg-secondary rounded-full h-1.5">
                    <div
                      className="bg-cyan-500 h-1.5 rounded-full transition-all"
                      style={{ width: `${shot.confidence * 100}%` }}
                    ></div>
                  </div>
                </div>
                <span className="font-mono text-cyan-400">
                  {(shot.confidence * 100).toFixed(1)}%
                </span>
              </div>
              {shot.accel_x !== undefined && shot.gyro_x !== undefined && (
                <div className="mt-2 grid grid-cols-2 gap-2 text-xs text-gray-400">
                  <div>
                    Accel: {shot.accel_x?.toFixed(2)}, {shot.accel_y?.toFixed(2)}, {shot.accel_z?.toFixed(2)}
                  </div>
                  <div>
                    Gyro: {shot.gyro_x?.toFixed(2)}, {shot.gyro_y?.toFixed(2)}, {shot.gyro_z?.toFixed(2)}
                  </div>
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
