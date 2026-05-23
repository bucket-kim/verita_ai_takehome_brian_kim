import { BrowserRouter, Routes, Route, Navigate } from 'react-router';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import Invoices from './pages/Invoices';
import InvoiceDetail from './pages/InvoiceDetail';
import Layout from './components/Layout';
import OpsLogin from './pages/ops/OpsLogin';
import OpsCustomers from './pages/ops/OpsCustomers';
import OpsCustomerDetail from './pages/ops/OpsCustomerDetail';
import OpsInvoiceEdit from './pages/ops/OpsInvoiceEdit';

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
        <Route
          path="/ops/invoices/:id/edit"
          element={
            <OpsProtectedRoute>
              <OpsInvoiceEdit />
            </OpsProtectedRoute>
          }
        />
        <Route path="/" element={<Navigate to="/customer/dashboard" replace />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
