/**
 * IMUIntensityChart - Bar chart showing accelerometer/gyroscope intensity
 */
import React from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import { ShotEvent } from '@/types';

interface IMUIntensityChartProps {
  shots: ShotEvent[];
}

interface ChartData {
  index: number;
  accel_magnitude: number;
  gyro_magnitude: number;
  confidence: number;
}

export const IMUIntensityChart: React.FC<IMUIntensityChartProps> = ({
  shots,
}) => {
  const getChartData = (): ChartData[] => {
    return shots.slice(-20).map((shot, index) => ({
      index,
      accel_magnitude: Math.sqrt(
        (shot.accel_x || 0) ** 2 +
          (shot.accel_y || 0) ** 2 +
          (shot.accel_z || 0) ** 2
      ),
      gyro_magnitude: Math.sqrt(
        (shot.gyro_x || 0) ** 2 +
          (shot.gyro_y || 0) ** 2 +
          (shot.gyro_z || 0) ** 2
      ),
      confidence: shot.confidence,
    }));
  };

  const data = getChartData();

  if (data.length === 0) {
    return (
      <div className="w-full h-80 flex items-center justify-center text-gray-400">
        No IMU data available
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={320}>
      <BarChart data={data}>
        <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
        <XAxis dataKey="index" stroke="#64748b" />
        <YAxis stroke="#64748b" />
        <Tooltip
          contentStyle={{
            backgroundColor: '#1e293b',
            border: '1px solid #334155',
            borderRadius: '0.5rem',
          }}
        />
        <Legend />
        <Bar
          dataKey="accel_magnitude"
          fill="#ef4444"
          name="Accelerometer (m/s²)"
        />
        <Bar
          dataKey="gyro_magnitude"
          fill="#f59e0b"
          name="Gyroscope (°/s)"
        />
      </BarChart>
    </ResponsiveContainer>
  );
};
