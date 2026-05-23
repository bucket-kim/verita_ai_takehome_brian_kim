import { useState, useEffect, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import opsClient from '../../api/opsClient';
import type { OpsCustomerDetail } from '../../types/ops';
import CreditModal from '../../components/ops/CreditModal';

export default function OpsCustomerDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [customer, setCustomer] = useState<OpsCustomerDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [showCreditModal, setShowCreditModal] = useState(false);

  const fetchCustomer = async () => {
    if (!id) return;
    try {
      setLoading(true);
      const response = await opsClient.get(`/ops/customers/${id}`);
      setCustomer(response.data);
    } catch (error) {
      console.error('Failed to fetch customer:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCustomer();
  }, [id]);

  const dailyData = useMemo(() => {
    if (!customer) return [];

    const aggregated: Record<string, number> = {};

    customer.usage_data.forEach((dataPoint) => {
      const date = new Date(dataPoint.timestamp).toISOString().split('T')[0];
      aggregated[date] = (aggregated[date] || 0) + dataPoint.units;
    });

    return Object.entries(aggregated)
      .map(([date, units]) => ({ date, units }))
      .sort((a, b) => a.date.localeCompare(b.date));
  }, [customer]);

  const formatCurrency = (cents: number) => {
    return `$${(cents / 100).toFixed(2)}`;
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString();
  };

  const getStatusBadge = (status: string) => {
    const colors: Record<string, string> = {
      draft: 'bg-gray-100 text-gray-800',
      issued: 'bg-yellow-100 text-yellow-800',
      paid: 'bg-green-100 text-green-800',
    };

    return (
      <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${colors[status] || 'bg-gray-100 text-gray-800'}`}>
        {status}
      </span>
    );
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-gray-500">Loading...</div>
      </div>
    );
  }

  if (!customer) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-gray-500">Customer not found</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <button
          onClick={() => navigate('/ops/customers')}
          className="mb-4 text-blue-600 hover:text-blue-800"
        >
          ← Back to customers
        </button>

        <div className="mb-8">
          <div className="flex justify-between items-center">
            <h1 className="text-3xl font-bold text-gray-900">{customer.name}</h1>
            <button
              onClick={() => setShowCreditModal(true)}
              className="px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
            >
              Issue Credit
            </button>
          </div>
        </div>

        <div className="bg-white shadow overflow-hidden sm:rounded-lg mb-6">
          <div className="px-4 py-5 sm:px-6">
            <h3 className="text-lg leading-6 font-medium text-gray-900">Customer Information</h3>
          </div>
          <div className="border-t border-gray-200 px-4 py-5 sm:px-6">
            <dl className="grid grid-cols-1 gap-x-4 gap-y-6 sm:grid-cols-2">
              <div>
                <dt className="text-sm font-medium text-gray-500">Email</dt>
                <dd className="mt-1 text-sm text-gray-900">{customer.email}</dd>
              </div>
              <div>
                <dt className="text-sm font-medium text-gray-500">Customer ID</dt>
                <dd className="mt-1 text-sm text-gray-900 font-mono">{customer.id}</dd>
              </div>
              <div>
                <dt className="text-sm font-medium text-gray-500">Created</dt>
                <dd className="mt-1 text-sm text-gray-900">{formatDate(customer.created_at)}</dd>
              </div>
              <div>
                <dt className="text-sm font-medium text-gray-500">API Key Prefixes</dt>
                <dd className="mt-1 text-sm text-gray-900 font-mono">
                  {customer.api_key_prefixes.length > 0
                    ? customer.api_key_prefixes.map(prefix => `${prefix}***`).join(', ')
                    : 'None'}
                </dd>
              </div>
            </dl>
          </div>
        </div>

        <div className="bg-white rounded-lg shadow p-6 mb-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Usage (Last 30 Days)</h2>
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

        <div className="bg-white shadow overflow-hidden sm:rounded-lg mb-6">
          <div className="px-4 py-5 sm:px-6">
            <h3 className="text-lg leading-6 font-medium text-gray-900">Invoices</h3>
          </div>
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Period
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Total
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Status
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {customer.invoices.map((invoice) => (
                <tr key={invoice.id}>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                    {formatDate(invoice.period_start)} - {formatDate(invoice.period_end)}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                    {formatCurrency(invoice.total_cents)}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm">
                    {getStatusBadge(invoice.status)}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm">
                    <button
                      onClick={() => navigate(`/ops/invoices/${invoice.id}/edit`)}
                      className="text-blue-600 hover:text-blue-800"
                    >
                      Edit
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {customer.invoices.length === 0 && (
            <div className="text-center py-8 text-gray-500">
              No invoices found
            </div>
          )}
        </div>

        <div className="bg-white shadow overflow-hidden sm:rounded-lg">
          <div className="px-4 py-5 sm:px-6">
            <h3 className="text-lg leading-6 font-medium text-gray-900">Recent Audit Logs</h3>
          </div>
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Time
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Action
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Actor
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Reason
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {customer.audit_logs.map((log) => (
                <tr key={log.id}>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {formatDate(log.created_at)}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                    {log.entity_type} {log.action}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {log.actor}
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-500">
                    {log.reason}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {customer.audit_logs.length === 0 && (
            <div className="text-center py-8 text-gray-500">
              No audit logs found
            </div>
          )}
        </div>

        {showCreditModal && (
          <CreditModal
            customerId={customer.id}
            customerName={customer.name}
            onClose={() => setShowCreditModal(false)}
            onSuccess={() => {
              setShowCreditModal(false);
              fetchCustomer();
            }}
          />
        )}
      </div>
    </div>
  );
}
