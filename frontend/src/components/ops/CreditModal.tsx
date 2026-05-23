import { useState, type FormEvent } from 'react';
import opsClient from '../../api/opsClient';

interface CreditModalProps {
  customerId: string;
  customerName: string;
  onClose: () => void;
  onSuccess: () => void;
}

export default function CreditModal({ customerId, customerName, onClose, onSuccess }: CreditModalProps) {
  const [amount, setAmount] = useState('');
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
      const amountCents = Math.round(parseFloat(amount) * 100);

      // Generate idempotency key
      const idempotencyKey = crypto.randomUUID();

      await opsClient.post(
        `/ops/customers/${customerId}/credits`,
        {
          amount_cents: amountCents,
          reason: reason,
        },
        {
          headers: {
            'X-Idempotency-Key': idempotencyKey,
          },
        }
      );

      onSuccess();
    } catch (err) {
      console.error('Failed to issue credit:', err);
      setError('Failed to issue credit. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  const amountDollars = parseFloat(amount) || 0;

  return (
    <div className="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full flex items-center justify-center z-50">
      <div className="relative bg-white rounded-lg shadow-xl max-w-md w-full mx-4">
        <div className="px-6 py-4 border-b border-gray-200">
          <h3 className="text-lg font-medium text-gray-900">Issue Credit</h3>
        </div>

        <form onSubmit={handleSubmit} className="px-6 py-4">
          {error && (
            <div className="mb-4 bg-red-50 border border-red-200 rounded-md p-3">
              <p className="text-sm text-red-800">{error}</p>
            </div>
          )}

          <div className="mb-4">
            <label htmlFor="amount" className="block text-sm font-medium text-gray-700 mb-1">
              Amount (USD)
            </label>
            <div className="relative">
              <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                <span className="text-gray-500 sm:text-sm">$</span>
              </div>
              <input
                type="number"
                id="amount"
                name="amount"
                step="0.01"
                min="0.01"
                required
                className="pl-7 appearance-none block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm placeholder-gray-400 focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
                placeholder="0.00"
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
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
              placeholder="Enter reason for issuing credit"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
            />
          </div>

          {amount && reason && (
            <div className="mb-4 p-4 bg-yellow-50 border border-yellow-200 rounded-md">
              <p className="text-sm text-yellow-800 mb-3">
                You are about to issue a <strong>${amountDollars.toFixed(2)}</strong> credit to{' '}
                <strong>{customerName}</strong>. This cannot be undone.
              </p>
              <label className="flex items-start">
                <input
                  type="checkbox"
                  checked={confirmed}
                  onChange={(e) => setConfirmed(e.target.checked)}
                  className="mt-1 h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                />
                <span className="ml-2 text-sm text-gray-700">
                  I confirm that I want to issue this credit
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
              {submitting ? 'Processing...' : 'Issue Credit'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
