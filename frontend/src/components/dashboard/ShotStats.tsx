/**
 * ShotStats - KPI cards showing key metrics
 */
import React from 'react';
import { ShotStats as ShotStatsType } from '@/types';

interface ShotStatsProps {
  stats: ShotStatsType | null;
}

export const ShotStats: React.FC<ShotStatsProps> = ({ stats }) => {
  if (!stats) {
    return (
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="container-primary h-24 animate-pulse"></div>
        ))}
      </div>
    );
  }

  const timeDuration =
    stats.latest_ts && stats.earliest_ts
      ? Math.round((stats.latest_ts - stats.earliest_ts) / 1000)
      : 0;

  const shotRate =
    timeDuration > 0
      ? ((stats.total_shots / timeDuration) * 60).toFixed(1)
      : '0';

  return (
    <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
      <div className="container-primary card-hover">
        <div className="text-gray-400 text-sm mb-2">Total Shots</div>
        <div className="text-3xl font-bold text-accent">
          {stats.total_shots}
        </div>
      </div>

      <div className="container-primary card-hover">
        <div className="text-gray-400 text-sm mb-2">Avg Confidence</div>
        <div className="text-3xl font-bold text-cyan-400">
          {(stats.avg_confidence * 100).toFixed(1)}%
        </div>
      </div>

      <div className="container-primary card-hover">
        <div className="text-gray-400 text-sm mb-2">Shot Rate</div>
        <div className="text-3xl font-bold text-violet-400">
          {shotRate}
          <span className="text-lg text-gray-400 ml-1">/min</span>
        </div>
      </div>

      <div className="container-primary card-hover">
        <div className="text-gray-400 text-sm mb-2">Duration</div>
        <div className="text-3xl font-bold text-emerald-400">
          {timeDuration}
          <span className="text-lg text-gray-400 ml-1">s</span>
        </div>
      </div>
    </div>
  );
};
