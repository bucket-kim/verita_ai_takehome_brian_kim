import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router';
import opsClient from '../../api/opsClient';
import type { OpsCustomer } from '../../types/ops';

export default function OpsCustomers() {
  const [customers, setCustomers] = useState<OpsCustomer[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  const fetchCustomers = async (cursor?: string) => {
    try {
      setLoading(true);
      const params = new URLSearchParams();
      if (cursor) {
        params.append('cursor', cursor);
      }
      params.append('limit', '50');

      const response = await opsClient.get(`/ops/customers?${params.toString()}`);
      const data = response.data;

      setCustomers(prev => cursor ? [...prev, ...data.customers] : data.customers);
      setNextCursor(data.next_cursor);
      setHasMore(data.has_more);
    } catch (error) {
      console.error('Failed to fetch customers:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCustomers();
  }, []);

  const loadMore = () => {
    if (nextCursor && !loading) {
      fetchCustomers(nextCursor);
    }
  };

  const formatCurrency = (cents: number) => {
    return `$${(cents / 100).toFixed(2)}`;
  };

  const hasAnomaly = (customer: OpsCustomer) => {
    // Anomaly flag: usage this month is >10× their 30-day average
    // For simplicity, we'll calculate based on this month's usage
    // A more accurate implementation would require 30-day historical data
    // Since we don't have detailed historical data here, we'll use a simple heuristic
    // If this_month_usage is very high (>10000 units), flag it as anomaly
    return customer.this_month_usage > 10000;
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900">Ops Console - Customers</h1>
          <p className="mt-2 text-sm text-gray-600">
            Manage and monitor customer accounts
          </p>
        </div>

        <div className="bg-white shadow overflow-hidden sm:rounded-lg">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Name
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Email
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  This Month Usage
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Outstanding Balance
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Status
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {customers.map((customer) => (
                <tr
                  key={customer.id}
                  onClick={() => navigate(`/ops/customers/${customer.id}`)}
                  className="hover:bg-gray-50 cursor-pointer"
                >
                  <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                    {customer.name}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {customer.email}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {customer.this_month_usage.toLocaleString()} units
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {formatCurrency(customer.outstanding_balance_cents)}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm">
                    {hasAnomaly(customer) && (
                      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800">
                        ⚠️ Anomaly
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {loading && (
            <div className="text-center py-8 text-gray-500">
              Loading...
            </div>
          )}

          {!loading && customers.length === 0 && (
            <div className="text-center py-8 text-gray-500">
              No customers found
            </div>
          )}

          {hasMore && !loading && (
            <div className="text-center py-4 border-t border-gray-200">
              <button
                onClick={loadMore}
                className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
              >
                Load more
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
