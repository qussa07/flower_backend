BEGIN;

CREATE OR REPLACE FUNCTION hide_out_of_stock_product()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.count = 0 THEN
        NEW."isShow" := false;
        NEW."isShowCase" := false;
    END IF;
    RETURN NEW;
END;
$$;

CREATE OR REPLACE TRIGGER products_hide_out_of_stock
BEFORE INSERT OR UPDATE OF count, "isShow", "isShowCase" ON products
FOR EACH ROW
EXECUTE FUNCTION hide_out_of_stock_product();

UPDATE products
SET "isShow" = false, "isShowCase" = false
WHERE count = 0 AND ("isShow" OR "isShowCase");

COMMIT;
