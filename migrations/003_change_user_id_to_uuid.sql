BEGIN;

DO $$
DECLARE
    users_table_oid REGCLASS := to_regclass('users');
    primary_key_name TEXT;
    id_data_type TEXT;
BEGIN
    IF users_table_oid IS NULL THEN
        RAISE EXCEPTION 'Table users does not exist in the current schema';
    END IF;

    SELECT data_type
    INTO id_data_type
    FROM information_schema.columns
    WHERE table_schema = current_schema()
      AND table_name = 'users'
      AND column_name = 'id';

    IF id_data_type IS NULL THEN
        RAISE EXCEPTION 'Column users.id does not exist';
    END IF;

    IF id_data_type = 'uuid' THEN
        RAISE NOTICE 'users.id is already UUID; no migration needed';
        RETURN;
    END IF;

    IF EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE contype = 'f'
          AND confrelid = users_table_oid
    ) THEN
        RAISE EXCEPTION
            'A foreign key references users. Migrate referencing columns together with users.id.';
    END IF;

    SELECT constraint_name
    INTO primary_key_name
    FROM information_schema.table_constraints
    WHERE table_schema = current_schema()
      AND table_name = 'users'
      AND constraint_type = 'PRIMARY KEY';

    IF primary_key_name IS NULL THEN
        RAISE EXCEPTION 'users table has no primary key';
    END IF;

    ALTER TABLE users
        ADD COLUMN id_uuid UUID NOT NULL DEFAULT gen_random_uuid();

    EXECUTE format('ALTER TABLE users DROP CONSTRAINT %I', primary_key_name);
    ALTER TABLE users DROP COLUMN id;
    ALTER TABLE users RENAME COLUMN id_uuid TO id;
    ALTER TABLE users ADD CONSTRAINT users_pkey PRIMARY KEY (id);

    ALTER TABLE users ALTER COLUMN id DROP DEFAULT;
END $$;

COMMIT;
