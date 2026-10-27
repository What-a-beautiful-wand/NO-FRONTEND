CREATE TABLE IF NOT EXISTS store_products (
    id BIGSERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    group_name TEXT NOT NULL,
    price INTEGER NOT NULL CHECK (price > 0),
    img_name TEXT NOT NULL,
    img_href TEXT NOT NULL,
    is_favorite BOOLEAN NOT NULL DEFAULT FALSE,
    year INTEGER NOT NULL CHECK (year > 0),
    duration TEXT NOT NULL,
    quantity INTEGER NOT NULL CONSTRAINT store_products_quantity_check CHECK (quantity >= 0)
);

-- Permit sold-out records in a database created by the original server.
ALTER TABLE store_products DROP CONSTRAINT IF EXISTS store_products_quantity_check;
ALTER TABLE store_products ADD CONSTRAINT store_products_quantity_check CHECK (quantity >= 0);

CREATE TABLE IF NOT EXISTS store_messages (
    id BIGSERIAL PRIMARY KEY,
    email TEXT NOT NULL,
    tel TEXT NOT NULL DEFAULT '',
    problem_text TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Remember applied demo datasets, so deleted products stay deleted after a restart.
CREATE TABLE IF NOT EXISTS store_seed_history (
    name TEXT PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
