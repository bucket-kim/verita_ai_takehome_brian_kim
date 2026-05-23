import axios from 'axios';

const opsClient = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000',
});

// Add ops token from localStorage to all requests
opsClient.interceptors.request.use((config) => {
  const opsToken = localStorage.getItem('opsToken');
  if (opsToken) {
    config.headers['X-Ops-Token'] = opsToken;
  }
  return config;
});

// Handle 401 responses by redirecting to ops login
opsClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('opsToken');
      window.location.href = '/ops/login';
    }
    return Promise.reject(error);
  }
);

export default opsClient;
