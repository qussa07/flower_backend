-- Existing orders start in progress; only paid orders appear in the staff queue.
DO $$ BEGIN
    CREATE TYPE completion_status AS ENUM ('in_progress', 'completed');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

ALTER TABLE orders ADD COLUMN IF NOT EXISTS completion_status completion_status
    NOT NULL DEFAULT 'in_progress';

CREATE INDEX IF NOT EXISTS ix_orders_staff_queue
    ON orders (created_at, id)
    WHERE payment_status = 'paid' AND completion_status = 'in_progress';
