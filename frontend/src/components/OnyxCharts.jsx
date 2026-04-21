/**
 * OnyxCharts — live chart panels for the ONYX dashboard.
 * Uses recharts. Install: npm install recharts
 */
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  LineChart, Line, AreaChart, Area, Cell,
} from 'recharts';

const SHOT_HEX = {
  Forehand: '#00e5a0',
  Backhand: '#4f8cff',
  Smash:    '#ff5c5c',
  Volley:   '#ffb347',
  Bandeja:  '#b464ff',
  Lob:      '#64dcff',
};

const SHOT_TYPES = ['Forehand', 'Backhand', 'Smash', 'Volley', 'Bandeja', 'Lob'];

const tooltipStyle = {
  backgroundColor: '#111318',
  border: '0.5px solid rgba(255,255,255,0.1)',
  borderRadius: 6,
  fontSize: 11,
  fontFamily: 'DM Mono, monospace',
  color: '#e8eaf0',
};

export function DistributionChart({ byType }) {
  const data = SHOT_TYPES.map(t => ({ name: t, count: byType[t] ?? 0 }));
  return (
    <ResponsiveContainer width="100%" height={150}>
      <BarChart data={data} barSize={18} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
        <XAxis dataKey="name" tick={{ fontSize: 9, fill: '#6b7280', fontFamily: 'DM Mono, monospace' }} axisLine={false} tickLine={false} />
        <YAxis tick={{ fontSize: 9, fill: '#6b7280', fontFamily: 'DM Mono, monospace' }} axisLine={false} tickLine={false} allowDecimals={false} />
        <Tooltip contentStyle={tooltipStyle} cursor={{ fill: 'rgba(255,255,255,0.03)' }} />
        <Bar dataKey="count" radius={[3, 3, 0, 0]}>
          {data.map((entry) => (
            <Cell key={entry.name} fill={SHOT_HEX[entry.name]} fillOpacity={0.85} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

export function RateChart({ rateHistory }) {
  const data = rateHistory.length
    ? rateHistory.map((b, i) => ({ i, rate: b.count }))
    : Array(8).fill(null).map((_, i) => ({ i, rate: 0 }));

  return (
    <ResponsiveContainer width="100%" height={150}>
      <AreaChart data={data} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
        <defs>
          <linearGradient id="rateGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%"  stopColor="#4f8cff" stopOpacity={0.3} />
            <stop offset="95%" stopColor="#4f8cff" stopOpacity={0}   />
          </linearGradient>
        </defs>
        <XAxis hide />
        <YAxis tick={{ fontSize: 9, fill: '#6b7280', fontFamily: 'DM Mono, monospace' }} axisLine={false} tickLine={false} allowDecimals={false} />
        <Tooltip contentStyle={tooltipStyle} formatter={(v) => [`${v} shots`, '10s window']} />
        <Area type="monotone" dataKey="rate" stroke="#4f8cff" strokeWidth={1.5} fill="url(#rateGrad)" dot={false} />
      </AreaChart>
    </ResponsiveContainer>
  );
}

export function ConfidenceChart({ shots }) {
  const data = [...shots].reverse().slice(-40).map((s, i) => ({
    i,
    conf: Math.round(s.confidence * 100),
    type: s.type,
  }));

  return (
    <ResponsiveContainer width="100%" height={90}>
      <LineChart data={data} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
        <XAxis hide />
        <YAxis domain={[0, 100]} tick={{ fontSize: 9, fill: '#6b7280', fontFamily: 'DM Mono, monospace' }} axisLine={false} tickLine={false} />
        <Tooltip
          contentStyle={tooltipStyle}
          formatter={(v, _, props) => [`${v}% — ${props.payload.type}`, 'Confidence']}
        />
        <Line
          type="monotone"
          dataKey="conf"
          stroke="#00e5a0"
          strokeWidth={1.5}
          dot={false}
          activeDot={{ r: 3, fill: '#00e5a0' }}
          isAnimationActive={false}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
