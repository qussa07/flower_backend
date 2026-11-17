-- Apply after migration 007, before starting the updated application.
BEGIN;

-- Preserve the stock from migration 006 when adopting the API field name.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = current_schema() AND table_name = 'products'
          AND column_name = 'quantity'
    ) AND NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = current_schema() AND table_name = 'products'
          AND column_name = 'count'
    ) THEN
        ALTER TABLE products RENAME COLUMN quantity TO count;
    END IF;
END $$;

ALTER TABLE products ADD COLUMN IF NOT EXISTS count INTEGER NOT NULL DEFAULT 0;
ALTER TABLE products ADD COLUMN IF NOT EXISTS "isShow" BOOLEAN NOT NULL DEFAULT false;

-- Keep existing values if isShow was previously a generated column.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = current_schema() AND table_name = 'products'
          AND column_name = 'isShow' AND is_generated = 'ALWAYS'
    ) THEN
        ALTER TABLE products ALTER COLUMN "isShow" DROP EXPRESSION;
    END IF;
END $$;

ALTER TABLE products ADD COLUMN IF NOT EXISTS "isShowCase" BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE products DROP CONSTRAINT IF EXISTS ck_products_count_nonnegative;
ALTER TABLE products ADD CONSTRAINT ck_products_count_nonnegative CHECK (count >= 0);

COMMIT;
