-- Apply before starting the application with the renamed ORM model.
BEGIN;
ALTER TABLE bouquets RENAME TO products;
ALTER TABLE compounds RENAME COLUMN id_bouquet TO id_product;
ALTER INDEX IF EXISTS bouquets_search_idx RENAME TO products_search_idx;
ALTER INDEX IF EXISTS bouquets_title_trgm_idx RENAME TO products_title_trgm_idx;
ALTER INDEX IF EXISTS ix_bouquets_id RENAME TO ix_products_id;
ALTER INDEX IF EXISTS ix_bouquets_title RENAME TO ix_products_title;
ALTER INDEX IF EXISTS ix_compounds_id_bouquet RENAME TO ix_compounds_id_product;
COMMIT;