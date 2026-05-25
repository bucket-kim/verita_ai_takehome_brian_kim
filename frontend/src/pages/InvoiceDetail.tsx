import { useParams, Link } from 'react-router';
import { useInvoiceDetail } from '../hooks/useInvoices';
import { formatMoney, formatMillicents } from '../types';

export default function InvoiceDetail() {
  const { id } = useParams<{ id: string }>();
  const { invoice, loading, error } = useInvoiceDetail(id!);

  const getStatusBadgeClass = (status: string) => {
    switch (status) {
      case 'paid':
        return 'bg-green-100 text-green-800';
      case 'issued':
        return 'bg-blue-100 text-blue-800';
      case 'draft':
        return 'bg-gray-100 text-gray-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  if (loading) {
    return (
      <div className="animate-pulse">
        <div className="h-8 bg-gray-200 rounded w-1/4 mb-6"></div>
        <div className="h-64 bg-gray-200 rounded"></div>
      </div>
    );
  }

  if (error || !invoice) {
    return (
      <div>
        <Link to="/customer/invoices" className="text-blue-600 hover:text-blue-900 mb-4 inline-block">
          ← Back to Invoices
        </Link>
        <div className="bg-red-50 border border-red-200 rounded-md p-4">
          <p className="text-red-800">{error || 'Invoice not found'}</p>
        </div>
      </div>
    );
  }

  return (
    <div>
      <Link to="/customer/invoices" className="text-blue-600 hover:text-blue-900 mb-4 inline-block">
        ← Back to Invoices
      </Link>

      <div className="bg-transparent rounded-lg p-6 mb-6">
        <div className="flex justify-between items-start mb-6">
          <div>
            <h1 className="text-6xl font-light text-gray-900 mb-6">Invoice #{invoice.id.slice(0, 8)}</h1>
            <p className="text-gray-600">
              Period: {new Date(invoice.period_start).toLocaleDateString()} -{' '}
              {new Date(invoice.period_end).toLocaleDateString()}
            </p>
          </div>
          <div className="text-right">
            <span
              className={`px-3 py-1 inline-flex text-sm leading-5 font-semibold rounded-full ${getStatusBadgeClass(
                invoice.status
              )}`}
            >
              {invoice.status}
            </span>
            <p className="text-6xl font-light text-gray-900 mb-6">{formatMoney(invoice.total_cents)}</p>
          </div>
        </div>

        {invoice.paid_at && (
          <p className="text-sm text-gray-600 mb-4">
            Paid on {new Date(invoice.paid_at).toLocaleDateString()}
          </p>
        )}
      </div>

      <div className="bg-transparent  rounded-lg overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-200">
          <h2 className="text-lg font-semibold text-gray-900">Line Items</h2>
        </div>
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Description
              </th>
              <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                Units
              </th>
              <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                Unit Price
              </th>
              <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                Total
              </th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {invoice.line_items.map((item) => (
              <tr key={item.id}>
                <td className="px-6 py-4 text-sm text-gray-900">
                  {item.description}
                  {item.overridden && (
                    <span className="ml-2 text-xs text-amber-600">(adjusted)</span>
                  )}
                </td>
                <td className="px-6 py-4 text-sm text-gray-900 text-right">
                  {item.units.toLocaleString()}
                </td>
                <td className="px-6 py-4 text-sm text-gray-900 text-right">
                  {formatMillicents(item.unit_price_millicents)}
                </td>
                <td className="px-6 py-4 text-sm font-medium text-gray-900 text-right">
                  {formatMoney(item.total_cents)}
                </td>
              </tr>
            ))}
            <tr className="bg-gray-50">
              <td colSpan={3} className="px-6 py-4 text-sm font-semibold text-gray-900 text-right">
                Total
              </td>
              <td className="px-6 py-4 text-sm font-bold text-gray-900 text-right">
                {formatMoney(invoice.total_cents)}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  );
}
