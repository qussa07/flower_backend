-- Run once before starting the updated application. Safe to re-run.
-- Enum changes must commit before the new labels are used.
BEGIN;
ALTER TYPE payment_status ADD VALUE IF NOT EXISTS 'cancelled';
ALTER TYPE payment_status ADD VALUE IF NOT EXISTS 'refunded';
COMMIT;

BEGIN;
ALTER TABLE orders ADD COLUMN IF NOT EXISTS customer_email VARCHAR(254);
ALTER TABLE orders ADD COLUMN IF NOT EXISTS checkout_key UUID;
ALTER TABLE orders ADD COLUMN IF NOT EXISTS checkout_hash VARCHAR(64);
ALTER TABLE orders ADD COLUMN IF NOT EXISTS delivery_fee NUMERIC(12,2) NOT NULL DEFAULT 0;
ALTER TABLE orders ADD COLUMN IF NOT EXISTS stock_reserved BOOLEAN NOT NULL DEFAULT false;
CREATE UNIQUE INDEX IF NOT EXISTS uq_orders_checkout ON orders (customer_id, checkout_key);

CREATE TABLE IF NOT EXISTS payment_attempts (
    id UUID PRIMARY KEY,
    order_id UUID NOT NULL REFERENCES orders(id),
    provider_payment_id VARCHAR(255) UNIQUE,
    status VARCHAR(32) NOT NULL DEFAULT 'creating',
    request_payload JSONB NOT NULL,
    confirmation_url VARCHAR(2048),
    test BOOLEAN,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_payment_attempts_order_id ON payment_attempts(order_id);
CREATE INDEX IF NOT EXISTS ix_payment_attempts_status ON payment_attempts(status);

CREATE TABLE IF NOT EXISTS payment_refunds (
    id UUID PRIMARY KEY,
    payment_attempt_id UUID NOT NULL REFERENCES payment_attempts(id),
    provider_refund_id VARCHAR(255) UNIQUE,
    amount NUMERIC(12,2) NOT NULL CHECK(amount > 0),
    status VARCHAR(32) NOT NULL DEFAULT 'creating',
    request_payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
ALTER TABLE payment_refunds ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT now();
CREATE INDEX IF NOT EXISTS ix_payment_refunds_payment_attempt_id ON payment_refunds(payment_attempt_id);
CREATE INDEX IF NOT EXISTS ix_payment_refunds_status ON payment_refunds(status);
COMMIT;
