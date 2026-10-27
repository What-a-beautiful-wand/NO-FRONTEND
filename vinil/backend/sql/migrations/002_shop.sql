ALTER TABLE store_products
    ADD COLUMN genre TEXT NOT NULL DEFAULT 'Rock',
    ADD COLUMN description TEXT NOT NULL DEFAULT '',
    ADD COLUMN label TEXT NOT NULL DEFAULT '',
    ADD COLUMN format TEXT NOT NULL DEFAULT 'LP' CHECK (format IN ('LP', '2LP', 'EP', 'Single')),
    ADD COLUMN rpm INTEGER NOT NULL DEFAULT 33 CHECK (rpm IN (33, 45)),
    ADD COLUMN condition TEXT NOT NULL DEFAULT 'new' CHECK (condition IN ('new', 'used')),
    ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT TRUE,
    ADD COLUMN created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ADD COLUMN updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW();

CREATE TABLE store_users (
    id BIGSERIAL PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    phone TEXT NOT NULL DEFAULT '',
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'customer' CHECK (role IN ('customer', 'admin')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE store_sessions (
    token_hash TEXT PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES store_users(id) ON DELETE CASCADE,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX ON store_sessions(user_id);
CREATE INDEX ON store_sessions(expires_at);
CREATE TABLE store_login_attempts (
    email TEXT PRIMARY KEY,
    failures INTEGER NOT NULL,
    window_started TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE store_favorites (
    user_id BIGINT NOT NULL REFERENCES store_users(id) ON DELETE CASCADE,
    product_id BIGINT NOT NULL REFERENCES store_products(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, product_id)
);
CREATE TABLE store_cart_items (
    user_id BIGINT NOT NULL REFERENCES store_users(id) ON DELETE CASCADE,
    product_id BIGINT NOT NULL REFERENCES store_products(id),
    quantity INTEGER NOT NULL CHECK (quantity BETWEEN 1 AND 99),
    PRIMARY KEY (user_id, product_id)
);
CREATE TABLE store_orders (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES store_users(id),
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'processing', 'shipped', 'completed', 'cancelled')),
    payment_method TEXT NOT NULL CHECK (payment_method = 'on_receipt'),
    payment_status TEXT NOT NULL DEFAULT 'unpaid' CHECK (payment_status IN ('unpaid', 'paid')),
    shipping_method TEXT NOT NULL CHECK (shipping_method IN ('pickup', 'courier')),
    recipient_name TEXT NOT NULL,
    email TEXT NOT NULL,
    phone TEXT NOT NULL,
    address TEXT NOT NULL,
    comment TEXT NOT NULL DEFAULT '',
    subtotal BIGINT NOT NULL CHECK (subtotal > 0),
    delivery_fee BIGINT NOT NULL CHECK (delivery_fee >= 0),
    total BIGINT NOT NULL CHECK (total = subtotal + delivery_fee),
    currency TEXT NOT NULL DEFAULT 'RUB' CHECK (currency = 'RUB'),
    idempotency_key TEXT NOT NULL,
    request_hash TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, idempotency_key)
);
CREATE INDEX ON store_orders(user_id, created_at DESC);
CREATE INDEX ON store_orders(status, created_at DESC);
CREATE TABLE store_order_items (
    id BIGSERIAL PRIMARY KEY,
    order_id BIGINT NOT NULL REFERENCES store_orders(id),
    product_id BIGINT NOT NULL REFERENCES store_products(id),
    title TEXT NOT NULL,
    group_name TEXT NOT NULL,
    img_href TEXT NOT NULL,
    unit_price INTEGER NOT NULL CHECK (unit_price > 0),
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    line_total BIGINT NOT NULL CHECK (line_total = unit_price * quantity)
);
CREATE INDEX ON store_order_items(order_id);
CREATE TABLE store_order_events (
    id BIGSERIAL PRIMARY KEY,
    order_id BIGINT NOT NULL REFERENCES store_orders(id),
    status TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX ON store_order_events(order_id);
ALTER TABLE store_messages
    ADD COLUMN status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'resolved'));
CREATE INDEX ON store_products(group_name);
CREATE INDEX ON store_products(genre);
