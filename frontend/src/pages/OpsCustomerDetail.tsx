import { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router';
import opsClient from '../api/ops';

interface Customer {
  id: string;
  name: string;
  email: string;
  created_at: string;
}

interface Invoice {
  id: string;
  period_start: string;
  period_end: string;
  status: string;
  total_cents: number;
  created_at: string;
  paid_at: string | null;
}

export default function OpsCustomerDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [customer, setCustomer] = useState<Customer | null>(null);
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [showCreditModal, setShowCreditModal] = useState(false);
  const [creditAmount, setCreditAmount] = useState('');
  const [creditReason, setCreditReason] = useState('');
  const [creditLoading, setCreditLoading] = useState(false);

  const fetchCustomerData = useCallback(async () => {
    try {
      setLoading(true);
      setError('');

      // Fetch customer details
      const customerResponse = await opsClient.get(`/ops/customers/${id}`);
      setCustomer(customerResponse.data);

      // Fetch customer invoices (using customer API key approach or ops endpoint)
      // For now, we'll use a simple approach
      setInvoices([]);

    } catch (err: unknown) {
      const errorMessage = err && typeof err === 'object' && 'response' in err
        ? (err as { response?: { data?: { error?: string } } }).response?.data?.error || 'Failed to load customer data'
        : 'Failed to load customer data';
      setError(errorMessage);
      console.error('Error fetching customer:', err);
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    if (id) {
      fetchCustomerData();
    }
  }, [id, fetchCustomerData]);

  const handleIssueCredit = async () => {
    if (!creditAmount || isNaN(Number(creditAmount))) {
      alert('Please enter a valid credit amount in dollars');
      return;
    }

    if (!creditReason.trim()) {
      alert('Please provide a reason for the credit');
      return;
    }

    try {
      setCreditLoading(true);
      const amountCents = Math.round(Number(creditAmount) * 100);

      await opsClient.post(`/ops/customers/${id}/credits`, {
        amount_cents: amountCents,
        reason: creditReason,
        created_by: 'ops'
      });

      alert('Credit issued successfully');
      setShowCreditModal(false);
      setCreditAmount('');
      setCreditReason('');
      fetchCustomerData();
    } catch (err: unknown) {
      const errorMessage = err && typeof err === 'object' && 'response' in err
        ? (err as { response?: { data?: { error?: string } } }).response?.data?.error || 'Failed to issue credit'
        : 'Failed to issue credit';
      alert(errorMessage);
      console.error('Error issuing credit:', err);
    } finally {
      setCreditLoading(false);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('opsToken');
    navigate('/ops/login');
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-100 flex items-center justify-center">
        <div className="text-xl">Loading customer data...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gray-100 flex items-center justify-center">
        <div className="bg-white p-8 rounded-lg shadow-md max-w-md">
          <h2 className="text-xl font-bold text-red-600 mb-4">Error</h2>
          <p className="text-gray-700 mb-4">{error}</p>
          <button
            onClick={() => navigate('/ops/customers')}
            className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
          >
            Back to Customers
          </button>
        </div>
      </div>
    );
  }

  if (!customer) {
    return (
      <div className="min-h-screen bg-gray-100 flex items-center justify-center">
        <div className="text-xl">Customer not found</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-100">
      {/* Navigation */}
      <nav className="bg-white shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between h-16 items-center">
            <div className="flex items-center space-x-4">
              <button
                onClick={() => navigate('/ops/customers')}
                className="text-blue-600 hover:text-blue-800"
              >
                ← Back to Customers
              </button>
              <h1 className="text-xl font-bold">Ops Console</h1>
            </div>
            <button
              onClick={handleLogout}
              className="px-4 py-2 text-sm text-gray-700 hover:text-gray-900"
            >
              Logout
            </button>
          </div>
        </div>
      </nav>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Customer Info Card */}
        <div className="bg-white shadow-sm rounded-lg p-6 mb-6">
          <div className="flex justify-between items-start mb-4">
            <div>
              <h2 className="text-2xl font-bold text-gray-900">{customer.name}</h2>
              <p className="text-gray-600 mt-1">{customer.email}</p>
              <p className="text-sm text-gray-500 mt-2">
                Customer since: {new Date(customer.created_at).toLocaleDateString()}
              </p>
            </div>
            <button
              onClick={() => setShowCreditModal(true)}
              className="px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700"
            >
              Issue Credit
            </button>
          </div>

          <div className="border-t pt-4 mt-4">
            <dl className="grid grid-cols-2 gap-4">
              <div>
                <dt className="text-sm font-medium text-gray-500">Customer ID</dt>
                <dd className="mt-1 text-sm text-gray-900 font-mono">{customer.id}</dd>
              </div>
              <div>
                <dt className="text-sm font-medium text-gray-500">Status</dt>
                <dd className="mt-1 text-sm text-green-600 font-semibold">Active</dd>
              </div>
            </dl>
          </div>
        </div>

        {/* Invoices Section */}
        <div className="bg-white shadow-sm rounded-lg p-6">
          <h3 className="text-lg font-bold text-gray-900 mb-4">Invoices</h3>
          {invoices.length === 0 ? (
            <p className="text-gray-500">No invoices found for this customer.</p>
          ) : (
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Period</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Total</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Created</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {invoices.map((invoice) => (
                  <tr key={invoice.id}>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {new Date(invoice.period_start).toLocaleDateString()} - {new Date(invoice.period_end).toLocaleDateString()}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className={`px-2 py-1 text-xs rounded ${
                        invoice.status === 'paid' ? 'bg-green-100 text-green-800' : 'bg-yellow-100 text-yellow-800'
                      }`}>
                        {invoice.status}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      ${(invoice.total_cents / 100).toFixed(2)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {new Date(invoice.created_at).toLocaleDateString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </main>

      {/* Credit Modal */}
      {showCreditModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 max-w-md w-full mx-4">
            <h3 className="text-lg font-bold mb-4">Issue Credit</h3>

            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Credit Amount (USD)
              </label>
              <input
                type="number"
                step="0.01"
                value={creditAmount}
                onChange={(e) => setCreditAmount(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="0.00"
              />
            </div>

            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Reason
              </label>
              <textarea
                value={creditReason}
                onChange={(e) => setCreditReason(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                rows={3}
                placeholder="Explain why this credit is being issued..."
              />
            </div>

            <div className="flex justify-end space-x-3">
              <button
                onClick={() => {
                  setShowCreditModal(false);
                  setCreditAmount('');
                  setCreditReason('');
                }}
                className="px-4 py-2 border border-gray-300 rounded text-gray-700 hover:bg-gray-50"
                disabled={creditLoading}
              >
                Cancel
              </button>
              <button
                onClick={handleIssueCredit}
                disabled={creditLoading}
                className="px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700 disabled:bg-gray-400"
              >
                {creditLoading ? 'Issuing...' : 'Issue Credit'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
