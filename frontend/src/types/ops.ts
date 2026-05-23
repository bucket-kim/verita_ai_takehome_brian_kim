export interface OpsCustomer {
  id: string;
  name: string;
  email: string;
  created_at: string;
  this_month_usage: number;
  outstanding_balance_cents: number;
}

export interface OpsCustomerDetail {
  id: string;
  name: string;
  email: string;
  created_at: string;
  api_key_prefixes: string[];
  usage_data: UsageDataPoint[];
  invoices: Invoice[];
  audit_logs: AuditLog[];
}

export interface UsageDataPoint {
  timestamp: string;
  units: number;
}

export interface Invoice {
  id: string;
  period_start: string;
  period_end: string;
  status: string;
  total_cents: number;
  created_at: string;
  paid_at: string | null;
}

export interface InvoiceDetail {
  id: string;
  customer_id: string;
  customer_name: string;
  period_start: string;
  period_end: string;
  status: string;
  total_cents: number;
  created_at: string;
  paid_at: string | null;
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

export interface AuditLog {
  id: number;
  entity_type: string;
  entity_id: string;
  action: string;
  actor: string;
  reason: string;
  created_at: string;
  before_value?: Record<string, unknown>;
  after_value?: Record<string, unknown>;
}
