import { useMemo } from 'react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { useUsage } from '../hooks/useUsage';
import { formatMoney } from '../types';

export default function Dashboard() {
  // Get current month date range
  const now = new Date();
  const start = new Date(now.getFullYear(), now.getMonth(), 1).toISOString();
  const end = new Date(now.getFullYear(), now.getMonth() + 1, 0, 23, 59, 59).toISOString();

  const { events, loading, error } = useUsage({ start, end });

  // Aggregate by day
  const dailyData = useMemo(() => {
    const aggregated: Record<string, number> = {};

    events.forEach((event) => {
      const date = new Date(event.event_timestamp).toISOString().split('T')[0];
      aggregated[date] = (aggregated[date] || 0) + event.units;
    });

    return Object.entries(aggregated)
      .map(([date, units]) => ({ date, units }))
      .sort((a, b) => a.date.localeCompare(b.date));
  }, [events]);

  // Calculate total units and estimated charge
  const totalUnits = useMemo(() => {
    return events.reduce((sum, event) => sum + event.units, 0);
  }, [events]);

  // Calculate estimated charge based on tiered pricing
  const estimatedCharge = useMemo(() => {
    let remaining = totalUnits;
    let totalMillicents = 0;

    // Tier 1: 0-10,000 units at 0 millicents
    const tier1 = Math.min(remaining, 10000);
    totalMillicents += tier1 * 0;
    remaining -= tier1;

    // Tier 2: 10,001-100,000 units at 100 millicents
    const tier2 = Math.min(remaining, 90000);
    totalMillicents += tier2 * 100;
    remaining -= tier2;

    // Tier 3: 100,001+ units at 50 millicents
    totalMillicents += remaining * 50;

    return totalMillicents / 10; // Convert millicents to cents
  }, [totalUnits]);

  const monthName = now.toLocaleString('default', { month: 'long', year: 'numeric' });

  if (loading) {
    return (
      <div className="animate-pulse">
        <div className="h-8 bg-gray-200 rounded w-1/3 mb-6"></div>
        <div className="h-64 bg-gray-200 rounded mb-6"></div>
        <div className="h-32 bg-gray-200 rounded"></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-md p-4">
        <p className="text-red-800">{error}</p>
      </div>
    );
  }

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-6">
        Current billing period: {monthName}
      </h1>

      <div className="bg-white rounded-lg shadow p-6 mb-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Daily Usage</h2>
        <ResponsiveContainer width="100%" height={300}>
          <AreaChart data={dailyData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis
              dataKey="date"
              tickFormatter={(value) => new Date(value).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
            />
            <YAxis />
            <Tooltip
              labelFormatter={(value) => new Date(value).toLocaleDateString()}
              formatter={(value) => [`${value} units`, 'Usage']}
            />
            <Area
              type="monotone"
              dataKey="units"
              stroke="#3b82f6"
              fill="#93c5fd"
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-sm font-medium text-gray-500 mb-2">Total Units This Period</h3>
          <p className="text-3xl font-bold text-gray-900">{totalUnits.toLocaleString()}</p>
        </div>
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-sm font-medium text-gray-500 mb-2">Estimated Charge</h3>
          <p className="text-3xl font-bold text-gray-900">{formatMoney(estimatedCharge)}</p>
        </div>
      </div>
    </div>
  );
}
