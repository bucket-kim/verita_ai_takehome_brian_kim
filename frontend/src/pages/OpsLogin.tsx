import { useState } from 'react';
import { useNavigate } from 'react-router';
import opsClient from '../api/ops';

export default function OpsLogin() {
  const [opsToken, setOpsToken] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      // Test the token by fetching customers
      const response = await opsClient.get('/ops/customers', {
        headers: { 'X-Ops-Token': opsToken }
      });

      if (response.status === 200) {
        localStorage.setItem('opsToken', opsToken);
        navigate('/ops/customers');
      }
    } catch (err) {
      setError('Invalid ops token. Please check your credentials.');
      console.error('Ops login error:', err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-100 flex items-center justify-center">
      <div className="bg-white p-8 rounded-lg shadow-md w-full max-w-md">
        <h1 className="text-2xl font-bold mb-6 text-center">Ops Console Login</h1>

        <form onSubmit={handleSubmit}>
          <div className="mb-4">
            <label htmlFor="opsToken" className="block text-sm font-medium text-gray-700 mb-2">
              Ops Token
            </label>
            <input
              type="password"
              id="opsToken"
              value={opsToken}
              onChange={(e) => setOpsToken(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="your-ops-token-here"
              required
            />
          </div>

          {error && (
            <div className="mb-4 p-3 bg-red-100 border border-red-400 text-red-700 rounded">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-blue-600 text-white py-2 px-4 rounded-md hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed"
          >
            {loading ? 'Logging in...' : 'Login'}
          </button>
        </form>

        <div className="mt-4 text-center text-sm text-gray-600">
          <a href="/customer/login" className="text-blue-600 hover:underline">
            Customer Login
          </a>
        </div>
      </div>
    </div>
  );
}
