import { useState, useEffect } from 'react';
import apiClient from '../api/client';
import type { Invoice, InvoicesResponse, InvoiceDetail } from '../types';

export const useInvoices = () => {
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchInvoices = async () => {
      try {
        setLoading(true);
        const response = await apiClient.get<InvoicesResponse>('/v1/invoices');
        setInvoices(response.data.invoices);
        setError(null);
      } catch (err) {
        setError('Failed to fetch invoices');
        console.error(err);
      } finally {
        setLoading(false);
      }
    };

    fetchInvoices();
  }, []);

  return { invoices, loading, error };
};

export const useInvoiceDetail = (id: string) => {
  const [invoice, setInvoice] = useState<InvoiceDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchInvoice = async () => {
      try {
        setLoading(true);
        const response = await apiClient.get<InvoiceDetail>(`/v1/invoices/${id}`);
        setInvoice(response.data);
        setError(null);
      } catch (err) {
        setError('Failed to fetch invoice details');
        console.error(err);
      } finally {
        setLoading(false);
      }
    };

    if (id) {
      fetchInvoice();
    }
  }, [id]);

  return { invoice, loading, error };
};
