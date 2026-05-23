import { BrowserRouter, Routes, Route, Navigate } from 'react-router';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import Invoices from './pages/Invoices';
import InvoiceDetail from './pages/InvoiceDetail';
import OpsLogin from './pages/OpsLogin';
import OpsCustomers from './pages/OpsCustomers';
import OpsCustomerDetail from './pages/OpsCustomerDetail';
import Layout from './components/Layout';

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const apiKey = localStorage.getItem('apiKey');

  if (!apiKey) {
    return <Navigate to="/customer/login" replace />;
  }

  return <Layout>{children}</Layout>;
}

function OpsProtectedRoute({ children }: { children: React.ReactNode }) {
  const opsToken = localStorage.getItem('opsToken');

  if (!opsToken) {
    return <Navigate to="/ops/login" replace />;
  }

  return <>{children}</>;
}

function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* Customer Routes */}
        <Route path="/customer/login" element={<Login />} />
        <Route
          path="/customer/dashboard"
          element={
            <ProtectedRoute>
              <Dashboard />
            </ProtectedRoute>
          }
        />
        <Route
          path="/customer/invoices"
          element={
            <ProtectedRoute>
              <Invoices />
            </ProtectedRoute>
          }
        />
        <Route
          path="/customer/invoices/:id"
          element={
            <ProtectedRoute>
              <InvoiceDetail />
            </ProtectedRoute>
          }
        />

        {/* Ops Routes */}
        <Route path="/ops/login" element={<OpsLogin />} />
        <Route
          path="/ops/customers"
          element={
            <OpsProtectedRoute>
              <OpsCustomers />
            </OpsProtectedRoute>
          }
        />
        <Route
          path="/ops/customers/:id"
          element={
            <OpsProtectedRoute>
              <OpsCustomerDetail />
            </OpsProtectedRoute>
          }
        />

        {/* Default Route */}
        <Route path="/" element={<Navigate to="/customer/dashboard" replace />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
