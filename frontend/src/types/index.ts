export interface Invoice {
  id: string;
  period_start: string;
  period_end: string;
  status: 'draft' | 'issued' | 'paid';
  total_cents: number;
  created_at: string;
  paid_at: string | null;
}

export interface InvoiceDetail extends Invoice {
  line_items: LineItem[];
}

export interface LineItem {
  id: number;
  description: string;
  units: number;
  unit_price_millicents: number;
  total_cents: number;
  overridden: boolean;
}

export interface UsageEvent {
  id: string;
  request_id: string;
  api_key_id: string;
  endpoint: string;
  units: number;
  event_timestamp: string;
  ingested_at: string;
}

export interface UsageResponse {
  events: UsageEvent[];
  next_cursor: string | null;
  has_more: boolean;
}

export interface InvoicesResponse {
  invoices: Invoice[];
}

// Helper to format cents to dollars
export const formatMoney = (cents: number): string => {
  return `$${(cents / 100).toFixed(2)}`;
};

// Helper to format millicents to dollars
export const formatMillicents = (millicents: number): string => {
  return `$${(millicents / 100000).toFixed(5)}`;
};
