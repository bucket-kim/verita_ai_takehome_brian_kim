import { useState, type FormEvent } from 'react';
import { useNavigate } from 'react-router';

export default function OpsLogin() {
  const [opsToken, setOpsToken] = useState('');
  const navigate = useNavigate();

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (opsToken.trim()) {
      localStorage.setItem('opsToken', opsToken.trim());
      navigate('/ops/customers');
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="max-w-md w-full space-y-8 p-8 bg-white rounded-lg shadow">
        <div>
          <h2 className="text-center text-3xl font-bold text-gray-900">
            Ops Console
          </h2>
          <p className="mt-2 text-center text-sm text-gray-600">
            Enter your ops token to access the admin panel
          </p>
        </div>
        <form className="mt-8 space-y-6" onSubmit={handleSubmit}>
          <div>
            <label htmlFor="opsToken" className="sr-only">
              Ops Token
            </label>
            <input
              id="opsToken"
              name="opsToken"
              type="password"
              required
              className="appearance-none relative block w-full px-3 py-2 border border-gray-300 placeholder-gray-500 text-gray-900 rounded-md focus:outline-none focus:ring-blue-500 focus:border-blue-500 focus:z-10 sm:text-sm"
              placeholder="Enter ops token"
              value={opsToken}
              onChange={(e) => setOpsToken(e.target.value)}
            />
          </div>

          <div>
            <button
              type="submit"
              className="group relative w-full flex justify-center py-2 px-4 border border-transparent text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
            >
              Sign in
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
