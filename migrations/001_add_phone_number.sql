BEGIN;

DO $$
DECLARE
    has_old_column BOOLEAN;
    has_new_column BOOLEAN;
BEGIN
    SELECT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND table_name = 'users'
          AND column_name = 'phone_numder'
    ) INTO has_old_column;

    SELECT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND table_name = 'users'
          AND column_name = 'phone_number'
    ) INTO has_new_column;

    IF has_old_column AND NOT has_new_column THEN
        ALTER TABLE users RENAME COLUMN phone_numder TO phone_number;
    ELSIF NOT has_new_column THEN
        ALTER TABLE users ADD COLUMN phone_number VARCHAR(16);
    END IF;
END $$;

CREATE UNIQUE INDEX IF NOT EXISTS uq_users_phone_number
    ON users (phone_number);

COMMIT;