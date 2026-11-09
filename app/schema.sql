DROP TABLE IF EXISTS order_items;
DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS menu_items;

CREATE TABLE menu_items (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name_en     TEXT NOT NULL,
    name_kn     TEXT,
    name_hi     TEXT,
    aliases     TEXT DEFAULT '',     -- comma-separated spoken variants
    category    TEXT NOT NULL,
    price       INTEGER NOT NULL,    -- in rupees
    veg         INTEGER DEFAULT 1,   -- 1 = veg, 0 = non-veg
    available   INTEGER DEFAULT 1,   -- 1 = in stock, 0 = out of stock
    description TEXT DEFAULT ''
);

CREATE TABLE orders (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id     TEXT NOT NULL,
    status         TEXT NOT NULL DEFAULT 'DRAFT',
        -- DRAFT, CONFIRMED, PREPARING, READY, DELIVERED, CANCELLED
    language       TEXT DEFAULT 'en-IN',
    order_type     TEXT DEFAULT 'dine-in',
    table_no       TEXT,
    notes          TEXT DEFAULT '',
    total          INTEGER DEFAULT 0,
    created_at     TEXT DEFAULT CURRENT_TIMESTAMP,
    confirmed_at   TEXT,
    customer_id    TEXT,
    channel        TEXT DEFAULT 'web',
    customer_name  TEXT,
    customer_phone TEXT,
    payment_mode   TEXT
);

CREATE TABLE order_items (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id     INTEGER NOT NULL,
    menu_item_id INTEGER NOT NULL,
    quantity     INTEGER NOT NULL,
    unit_price   INTEGER NOT NULL,
    notes        TEXT DEFAULT '',
    FOREIGN KEY (order_id) REFERENCES orders(id),
    FOREIGN KEY (menu_item_id) REFERENCES menu_items(id)
);
