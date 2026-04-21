/**
 * ShotDistributionChart - Pie chart showing shot type distribution
 */
import React from 'react';
import {
  PieChart,
  Pie,
  Cell,
  Legend,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import { ShotDistribution, ShotType } from '@/types';

interface ShotDistributionChartProps {
  data: ShotDistribution[];
}

const SHOT_COLORS: Record<ShotType, string> = {
  [ShotType.FOREHAND]: '#06b6d4',
  [ShotType.BACKHAND]: '#8b5cf6',
  [ShotType.SMASH]: '#ef4444',
  [ShotType.VOLLEY]: '#10b981',
  [ShotType.BANDEJA]: '#f59e0b',
  [ShotType.LOB]: '#3b82f6',
};

export const ShotDistributionChart: React.FC<ShotDistributionChartProps> = ({
  data,
}) => {
  if (data.length === 0) {
    return (
      <div className="w-full h-80 flex items-center justify-center text-gray-400">
        No shot data available
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={320}>
      <PieChart>
        <Pie
          data={data}
          dataKey="count"
          nameKey="shot_type"
          cx="50%"
          cy="50%"
          outerRadius={100}
          label={({ shot_type, count }) => `${shot_type}: ${count}`}
        >
          {data.map((entry) => (
            <Cell
              key={`cell-${entry.shot_type}`}
              fill={SHOT_COLORS[entry.shot_type]}
            />
          ))}
        </Pie>
        <Tooltip
          formatter={(value: unknown) =>
            `${value} shots`
          }
          contentStyle={{
            backgroundColor: '#1e293b',
            border: '1px solid #334155',
            borderRadius: '0.5rem',
          }}
        />
        <Legend />
      </PieChart>
    </ResponsiveContainer>
  );
};
