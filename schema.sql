-- ============================================================
-- AeroWash Database Schema
-- Run this in Supabase → SQL Editor
-- ============================================================

-- Clients table
CREATE TABLE IF NOT EXISTS clients (
  id              UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  name            TEXT NOT NULL,
  email           TEXT NOT NULL,
  phone           TEXT NOT NULL,
  company         TEXT DEFAULT '',
  ico             TEXT DEFAULT '',
  billing_address TEXT NOT NULL,
  created_at      TIMESTAMPTZ DEFAULT NOW(),
  updated_at      TIMESTAMPTZ DEFAULT NOW(),
  CONSTRAINT clients_email_unique UNIQUE (email)
);

-- Orders table
CREATE TABLE IF NOT EXISTS orders (
  id            UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  order_num     TEXT NOT NULL,
  client_id     UUID REFERENCES clients(id) ON DELETE SET NULL,
  location      TEXT NOT NULL,
  building_type TEXT DEFAULT 'office',
  floors        INT DEFAULT 1,
  facade_area   NUMERIC(10,2) NOT NULL DEFAULT 0,
  window_area   NUMERIC(10,2) NOT NULL DEFAULT 0,
  total_area    NUMERIC(10,2) GENERATED ALWAYS AS (facade_area + window_area) STORED,
  price_per_m2  NUMERIC(8,2) DEFAULT 39,
  total_price   NUMERIC(12,2) GENERATED ALWAYS AS ((facade_area + window_area) * 39) STORED,
  service_date  DATE,
  notes         TEXT DEFAULT '',
  status        TEXT DEFAULT 'new'
                CHECK (status IN ('new','confirmed','in_progress','completed','cancelled')),
  pdf_url       TEXT,
  created_at    TIMESTAMPTZ DEFAULT NOW(),
  updated_at    TIMESTAMPTZ DEFAULT NOW(),
  CONSTRAINT orders_num_unique UNIQUE (order_num)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_orders_client    ON orders(client_id);
CREATE INDEX IF NOT EXISTS idx_orders_status    ON orders(status);
CREATE INDEX IF NOT EXISTS idx_orders_created   ON orders(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_clients_email    ON clients(email);

-- Auto-update updated_at
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN NEW.updated_at = NOW(); RETURN NEW; END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE TRIGGER clients_updated_at
  BEFORE UPDATE ON clients FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE OR REPLACE TRIGGER orders_updated_at
  BEFORE UPDATE ON orders FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- Row Level Security (optional but recommended)
-- ALTER TABLE clients ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE orders  ENABLE ROW LEVEL SECURITY;

-- Storage bucket for PDFs (run separately or via Dashboard)
-- INSERT INTO storage.buckets (id, name, public) VALUES ('invoices', 'invoices', true);
