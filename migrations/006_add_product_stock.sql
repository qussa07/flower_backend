BEGIN;
ALTER TABLE products
    ADD COLUMN quantity INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN is_active BOOLEAN GENERATED ALWAYS AS (quantity > 0) STORED,
    ADD CONSTRAINT ck_products_quantity_nonnegative CHECK (quantity >= 0);
COMMIT;