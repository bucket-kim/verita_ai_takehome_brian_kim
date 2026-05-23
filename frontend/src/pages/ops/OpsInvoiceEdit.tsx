import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router';
import opsClient from '../../api/opsClient';
import type { InvoiceDetail, LineItem, AuditLog } from '../../types/ops';
import LineItemOverrideModal from '../../components/ops/LineItemOverrideModal';

export default function OpsInvoiceEdit() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [invoice, setInvoice] = useState<InvoiceDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedLineItem, setSelectedLineItem] = useState<LineItem | null>(null);
  const [lineItemAuditLogs, setLineItemAuditLogs] = useState<Record<number, AuditLog[]>>({});

  const fetchInvoice = async () => {
    if (!id) return;
    try {
      setLoading(true);
      const response = await opsClient.get(`/ops/invoices/${id}`);
      setInvoice(response.data);
    } catch (error) {
      console.error('Failed to fetch invoice:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchLineItemAuditLogs = async (lineItemId: number) => {
    if (!id) return;
    try {
      const response = await opsClient.get(`/ops/invoices/${id}/line-items/${lineItemId}/audit-logs`);
      setLineItemAuditLogs(prev => ({
        ...prev,
        [lineItemId]: response.data.audit_logs
      }));
    } catch (error) {
      console.error('Failed to fetch audit logs:', error);
    }
  };

  useEffect(() => {
    fetchInvoice();
  }, [id]);

  const formatCurrency = (cents: number) => {
    return `$${(cents / 100).toFixed(2)}`;
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString();
  };

  const handleOverrideSuccess = (lineItemId: number) => {
    setSelectedLineItem(null);
    fetchInvoice();
    fetchLineItemAuditLogs(lineItemId);
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-gray-500">Loading...</div>
      </div>
    );
  }

  if (!invoice) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-gray-500">Invoice not found</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <button
          onClick={() => navigate(`/ops/customers/${invoice.customer_id}`)}
          className="mb-4 text-blue-600 hover:text-blue-800"
        >
          ← Back to customer
        </button>

        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900">Edit Invoice</h1>
          <p className="mt-2 text-sm text-gray-600">
            {invoice.customer_name} - {formatDate(invoice.period_start)} to {formatDate(invoice.period_end)}
          </p>
        </div>

        <div className="bg-white shadow overflow-hidden sm:rounded-lg mb-6">
          <div className="px-4 py-5 sm:px-6">
            <h3 className="text-lg leading-6 font-medium text-gray-900">Invoice Details</h3>
          </div>
          <div className="border-t border-gray-200 px-4 py-5 sm:px-6">
            <dl className="grid grid-cols-1 gap-x-4 gap-y-6 sm:grid-cols-2">
              <div>
                <dt className="text-sm font-medium text-gray-500">Status</dt>
                <dd className="mt-1 text-sm text-gray-900">{invoice.status}</dd>
              </div>
              <div>
                <dt className="text-sm font-medium text-gray-500">Total</dt>
                <dd className="mt-1 text-sm text-gray-900 font-bold">{formatCurrency(invoice.total_cents)}</dd>
              </div>
            </dl>
          </div>
        </div>

        <div className="bg-white shadow overflow-hidden sm:rounded-lg mb-6">
          <div className="px-4 py-5 sm:px-6">
            <h3 className="text-lg leading-6 font-medium text-gray-900">Line Items</h3>
          </div>
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Description
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Units
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Unit Price
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
              {invoice.line_items.map((item) => (
                <tr key={item.id}>
                  <td className="px-6 py-4 text-sm text-gray-900">
                    {item.description}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {item.units.toLocaleString()}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {formatCurrency(item.unit_price_millicents / 10)}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900 font-medium">
                    {formatCurrency(item.total_cents)}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm">
                    {item.overridden && (
                      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                        Overridden
                      </span>
                    )}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm space-x-2">
                    <button
                      onClick={() => setSelectedLineItem(item)}
                      className="text-blue-600 hover:text-blue-800"
                    >
                      Override
                    </button>
                    {lineItemAuditLogs[item.id] ? (
                      <button
                        onClick={() => setLineItemAuditLogs(prev => {
                          const newLogs = { ...prev };
                          delete newLogs[item.id];
                          return newLogs;
                        })}
                        className="text-gray-600 hover:text-gray-800"
                      >
                        Hide Audit
                      </button>
                    ) : (
                      <button
                        onClick={() => fetchLineItemAuditLogs(item.id)}
                        className="text-gray-600 hover:text-gray-800"
                      >
                        View Audit
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {invoice.line_items.map((item) => (
            lineItemAuditLogs[item.id] && (
              <div key={`audit-${item.id}`} className="border-t border-gray-200 px-6 py-4 bg-gray-50">
                <h4 className="text-sm font-medium text-gray-900 mb-3">
                  Audit Trail for: {item.description}
                </h4>
                <div className="space-y-2">
                  {lineItemAuditLogs[item.id].map((log) => (
                    <div key={log.id} className="text-sm text-gray-600 bg-white p-3 rounded border border-gray-200">
                      <div className="flex justify-between mb-1">
                        <span className="font-medium">{log.action} by {log.actor}</span>
                        <span className="text-gray-500">{formatDate(log.created_at)}</span>
                      </div>
                      {log.before_value && (
                        <div className="text-xs">
                          Before: {formatCurrency((log.before_value as { total_cents: number }).total_cents)}
                        </div>
                      )}
                      {log.after_value && (
                        <div className="text-xs">
                          After: {formatCurrency((log.after_value as { total_cents: number }).total_cents)}
                        </div>
                      )}
                      {log.reason && (
                        <div className="text-xs mt-1">
                          Reason: <span className="italic">{log.reason}</span>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )
          ))}
        </div>

        {selectedLineItem && (
          <LineItemOverrideModal
            invoiceId={invoice.id}
            lineItem={selectedLineItem}
            onClose={() => setSelectedLineItem(null)}
            onSuccess={() => handleOverrideSuccess(selectedLineItem.id)}
          />
        )}
      </div>
    </div>
  );
}
