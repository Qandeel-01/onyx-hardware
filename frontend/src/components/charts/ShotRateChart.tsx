/**
 * ShotRateChart - Line chart showing shots over time
 */
import React from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import { ShotEvent } from '@/types';

interface ShotRateChartProps {
  shots: ShotEvent[];
}

interface ChartData {
  time: string;
  count: number;
  cumulative: number;
}

export const ShotRateChart: React.FC<ShotRateChartProps> = ({ shots }) => {
  const getChartData = (): ChartData[] => {
    if (shots.length === 0) return [];

    // Group shots by 30-second intervals
    const intervals = new Map<number, number>();
    shots.forEach((shot) => {
      const intervalKey = Math.floor(
        new Date(shot.created_at).getTime() / 30000
      );
      intervals.set(intervalKey, (intervals.get(intervalKey) || 0) + 1);
    });

    let cumulative = 0;
    return Array.from(intervals.entries())
      .sort(([a], [b]) => a - b)
      .map(([intervalKey, count]) => {
        cumulative += count;
        return {
          time: new Date(intervalKey * 30000).toLocaleTimeString(),
          count,
          cumulative,
        };
      });
  };

  const data = getChartData();

  if (data.length === 0) {
    return (
      <div className="w-full h-80 flex items-center justify-center text-gray-400">
        No shot data available
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={320}>
      <LineChart data={data}>
        <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
        <XAxis dataKey="time" stroke="#64748b" />
        <YAxis stroke="#64748b" />
        <Tooltip
          contentStyle={{
            backgroundColor: '#1e293b',
            border: '1px solid #334155',
            borderRadius: '0.5rem',
          }}
        />
        <Legend />
        <Line
          type="monotone"
          dataKey="count"
          stroke="#06b6d4"
          name="Shots per Interval"
          strokeWidth={2}
        />
        <Line
          type="monotone"
          dataKey="cumulative"
          stroke="#8b5cf6"
          name="Cumulative Shots"
          strokeWidth={2}
        />
      </LineChart>
    </ResponsiveContainer>
  );
};
