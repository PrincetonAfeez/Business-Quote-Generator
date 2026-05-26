-- Business Quote Generator academic schema summary
-- PostgreSQL-style SQL, simplified from the Django models.

CREATE TABLE company_profile (
  id BIGSERIAL PRIMARY KEY,
  owner_id BIGINT NOT NULL UNIQUE REFERENCES auth_user(id) ON DELETE CASCADE,
  business_name VARCHAR(200) NOT NULL,
  logo VARCHAR(255),
  address TEXT NOT NULL DEFAULT '',
  tax_id VARCHAR(80) NOT NULL DEFAULT '',
  default_tax_rate NUMERIC(5,2) NOT NULL DEFAULT 0.00 CHECK (default_tax_rate >= 0 AND default_tax_rate <= 100),
  default_terms TEXT NOT NULL DEFAULT '',
  default_validity_days INTEGER NOT NULL DEFAULT 30 CHECK (default_validity_days >= 1)
);

CREATE TABLE client (
  id BIGSERIAL PRIMARY KEY,
  owner_id BIGINT NOT NULL REFERENCES auth_user(id) ON DELETE CASCADE,
  name VARCHAR(200) NOT NULL,
  company VARCHAR(200) NOT NULL DEFAULT '',
  email VARCHAR(254) NOT NULL DEFAULT '',
  phone VARCHAR(50) NOT NULL DEFAULT '',
  billing_address TEXT NOT NULL DEFAULT '',
  notes TEXT NOT NULL DEFAULT '',
  created_at TIMESTAMPTZ NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL
);
CREATE UNIQUE INDEX unique_client_email_per_owner_nonempty ON client(owner_id, email) WHERE email <> '';

CREATE TABLE catalog_item (
  id BIGSERIAL PRIMARY KEY,
  owner_id BIGINT NOT NULL REFERENCES auth_user(id) ON DELETE CASCADE,
  name VARCHAR(200) NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  default_unit_price NUMERIC(12,2) NOT NULL DEFAULT 0.00 CHECK (default_unit_price >= 0),
  unit VARCHAR(20) NOT NULL DEFAULT 'each' CHECK (unit IN ('hour', 'day', 'each', 'sqft', 'word', 'page')),
  created_at TIMESTAMPTZ NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE quote_counter (
  id BIGSERIAL PRIMARY KEY,
  owner_id BIGINT NOT NULL REFERENCES auth_user(id) ON DELETE CASCADE,
  year INTEGER NOT NULL,
  last_number INTEGER NOT NULL DEFAULT 0 CHECK (last_number >= 0),
  CONSTRAINT unique_quote_counter_per_user_year UNIQUE (owner_id, year)
);

CREATE TABLE quote (
  id BIGSERIAL PRIMARY KEY,
  owner_id BIGINT NOT NULL REFERENCES auth_user(id) ON DELETE CASCADE,
  number VARCHAR(20) NOT NULL,
  client_id BIGINT NOT NULL REFERENCES client(id) ON DELETE RESTRICT,
  status VARCHAR(20) NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'sent', 'viewed', 'accepted', 'declined', 'expired')),
  issue_date DATE NOT NULL,
  expiry_date DATE NOT NULL CHECK (expiry_date > issue_date),
  tax_rate NUMERIC(5,2) NOT NULL DEFAULT 0.00 CHECK (tax_rate >= 0 AND tax_rate <= 100),
  discount_type VARCHAR(20) NOT NULL DEFAULT 'none' CHECK (discount_type IN ('none', 'percent', 'flat')),
  discount_value NUMERIC(12,2) NOT NULL DEFAULT 0.00 CHECK (discount_value >= 0),
  subtotal NUMERIC(12,2) NOT NULL DEFAULT 0.00,
  tax_amount NUMERIC(12,2) NOT NULL DEFAULT 0.00,
  discount_amount NUMERIC(12,2) NOT NULL DEFAULT 0.00,
  total NUMERIC(12,2) NOT NULL DEFAULT 0.00,
  notes TEXT NOT NULL DEFAULT '',
  terms TEXT NOT NULL DEFAULT '',
  public_token VARCHAR(32) UNIQUE,
  viewed_at TIMESTAMPTZ,
  accepted_at TIMESTAMPTZ,
  declined_at TIMESTAMPTZ,
  is_favorite BOOLEAN NOT NULL DEFAULT FALSE,
  archived_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL,
  CONSTRAINT unique_quote_number_per_user UNIQUE (owner_id, number)
);

CREATE TABLE quote_line_item (
  id BIGSERIAL PRIMARY KEY,
  quote_id BIGINT NOT NULL REFERENCES quote(id) ON DELETE CASCADE,
  catalog_item_id BIGINT REFERENCES catalog_item(id) ON DELETE SET NULL,
  description TEXT NOT NULL,
  quantity NUMERIC(12,2) NOT NULL DEFAULT 1.00 CHECK (quantity >= 0.01),
  unit_price NUMERIC(12,2) NOT NULL DEFAULT 0.00 CHECK (unit_price >= 0),
  line_total NUMERIC(12,2) NOT NULL DEFAULT 0.00,
  position INTEGER NOT NULL DEFAULT 0 CHECK (position >= 0)
);

CREATE TABLE activity_event (
  id BIGSERIAL PRIMARY KEY,
  quote_id BIGINT NOT NULL REFERENCES quote(id) ON DELETE CASCADE,
  event_type VARCHAR(20) NOT NULL CHECK (event_type IN ('created', 'sent', 'viewed', 'accepted', 'declined', 'duplicated', 'edited', 'expired')),
  timestamp TIMESTAMPTZ NOT NULL,
  metadata JSONB NOT NULL DEFAULT '{}'
);
