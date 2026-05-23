import { useState, type FormEvent } from 'react';
import opsClient from '../../api/opsClient';
import type { LineItem } from '../../types/ops';

interface LineItemOverrideModalProps {
  invoiceId: string;
  lineItem: LineItem;
  onClose: () => void;
  onSuccess: () => void;
}

export default function LineItemOverrideModal({ invoiceId, lineItem, onClose, onSuccess }: LineItemOverrideModalProps) {
  const [newTotal, setNewTotal] = useState('');
  const [reason, setReason] = useState('');
  const [confirmed, setConfirmed] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();

    if (!confirmed) {
      return;
    }

    setSubmitting(true);
    setError(null);

    try {
      const newTotalCents = Math.round(parseFloat(newTotal) * 100);

      await opsClient.patch(
        `/ops/invoices/${invoiceId}/line-items/${lineItem.id}`,
        {
          total_cents: newTotalCents,
          reason: reason,
        }
      );

      onSuccess();
    } catch (err) {
      console.error('Failed to override line item:', err);
      setError('Failed to override line item. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  const oldTotal = lineItem.total_cents / 100;
  const newTotalDollars = parseFloat(newTotal) || 0;

  return (
    <div className="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full flex items-center justify-center z-50">
      <div className="relative bg-white rounded-lg shadow-xl max-w-md w-full mx-4">
        <div className="px-6 py-4 border-b border-gray-200">
          <h3 className="text-lg font-medium text-gray-900">Override Line Item</h3>
          <p className="mt-1 text-sm text-gray-500">{lineItem.description}</p>
        </div>

        <form onSubmit={handleSubmit} className="px-6 py-4">
          {error && (
            <div className="mb-4 bg-red-50 border border-red-200 rounded-md p-3">
              <p className="text-sm text-red-800">{error}</p>
            </div>
          )}

          <div className="mb-4">
            <div className="text-sm text-gray-600 mb-2">
              Current total: <span className="font-medium">${oldTotal.toFixed(2)}</span>
            </div>
          </div>

          <div className="mb-4">
            <label htmlFor="newTotal" className="block text-sm font-medium text-gray-700 mb-1">
              New Total (USD)
            </label>
            <div className="relative">
              <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                <span className="text-gray-500 sm:text-sm">$</span>
              </div>
              <input
                type="number"
                id="newTotal"
                name="newTotal"
                step="0.01"
                min="0"
                required
                className="pl-7 appearance-none block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm placeholder-gray-400 focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
                placeholder="0.00"
                value={newTotal}
                onChange={(e) => setNewTotal(e.target.value)}
              />
            </div>
          </div>

          <div className="mb-4">
            <label htmlFor="reason" className="block text-sm font-medium text-gray-700 mb-1">
              Reason (required)
            </label>
            <textarea
              id="reason"
              name="reason"
              rows={3}
              required
              className="appearance-none block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm placeholder-gray-400 focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
              placeholder="Enter reason for override"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
            />
          </div>

          {newTotal && reason && (
            <div className="mb-4 p-4 bg-yellow-50 border border-yellow-200 rounded-md">
              <p className="text-sm text-yellow-800 mb-3">
                Override line item <strong>{lineItem.description}</strong> from{' '}
                <strong>${oldTotal.toFixed(2)}</strong> to{' '}
                <strong>${newTotalDollars.toFixed(2)}</strong>. Reason: {reason}. This will be logged.
              </p>
              <label className="flex items-start">
                <input
                  type="checkbox"
                  checked={confirmed}
                  onChange={(e) => setConfirmed(e.target.checked)}
                  className="mt-1 h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                />
                <span className="ml-2 text-sm text-gray-700">
                  I confirm that I want to override this line item
                </span>
              </label>
            </div>
          )}

          <div className="flex justify-end space-x-3">
            <button
              type="button"
              onClick={onClose}
              disabled={submitting}
              className="px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={!confirmed || submitting}
              className="px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {submitting ? 'Processing...' : 'Override'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
