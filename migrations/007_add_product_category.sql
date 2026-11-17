BEGIN;
ALTER TABLE products ADD COLUMN category_id UUID REFERENCES categories(id);
CREATE INDEX ix_products_category_id ON products (category_id);
COMMIT;