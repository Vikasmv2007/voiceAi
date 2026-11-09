DROP TABLE IF EXISTS feedback;
DROP TABLE IF EXISTS sessions;
DROP TABLE IF EXISTS order_items;
DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS menu_items;
DROP TABLE IF EXISTS staff;

CREATE TABLE menu_items (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name_en     TEXT NOT NULL,
    name_kn     TEXT,
    name_hi     TEXT,
    name_ta     TEXT,
    name_te     TEXT,
    aliases     TEXT DEFAULT '',     -- comma-separated spoken variants
    category    TEXT NOT NULL,
    price       INTEGER NOT NULL,    -- in rupees (before GST)
    veg         INTEGER DEFAULT 1,   -- 1 = veg, 0 = non-veg
    available   INTEGER DEFAULT 1,   -- 1 = in stock, 0 = out of stock
    description TEXT DEFAULT '',
    image_url   TEXT DEFAULT '',
    addons      TEXT DEFAULT '',     -- "Extra Cheese:15, Extra Chutney:10"
    stock       INTEGER,             -- NULL = unlimited; 0 = sold out
    active      INTEGER DEFAULT 1    -- 0 = removed from the menu (kept for old bills)
);

CREATE TABLE orders (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id     TEXT NOT NULL,
    status         TEXT NOT NULL DEFAULT 'DRAFT',
        -- DRAFT, AWAITING_CASH, AWAITING_UPI, CONFIRMED, PREPARING, READY, DELIVERED, CANCELLED
    language       TEXT DEFAULT 'en-IN',
    order_type     TEXT DEFAULT 'dine-in',
    table_no       TEXT,
    notes          TEXT DEFAULT '',
    subtotal       INTEGER DEFAULT 0,
    tax            INTEGER DEFAULT 0,
    total          INTEGER DEFAULT 0,  -- subtotal + tax
    created_at     TEXT DEFAULT CURRENT_TIMESTAMP,
    confirmed_at   TEXT,
    customer_id    TEXT,
    channel        TEXT DEFAULT 'web',
    customer_name  TEXT,
    customer_phone TEXT,
    payment_mode   TEXT,
    payment_ref    TEXT,               -- gateway payment id, when paid online
    gateway_qr_id  TEXT,               -- Razorpay QR / payment link id
    confirmed_by   TEXT,               -- staff member who confirmed the payment
    eta_minutes    INTEGER
);
CREATE INDEX idx_orders_customer ON orders(customer_id);
CREATE INDEX idx_orders_session ON orders(session_id);

CREATE TABLE order_items (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id     INTEGER NOT NULL,
    menu_item_id INTEGER NOT NULL,
    quantity     INTEGER NOT NULL,
    unit_price   INTEGER NOT NULL,     -- dish price + chosen add-ons
    notes        TEXT DEFAULT '',
    addons       TEXT DEFAULT '',      -- "Extra Cheese, Extra Chutney"
    FOREIGN KEY (order_id) REFERENCES orders(id),
    FOREIGN KEY (menu_item_id) REFERENCES menu_items(id)
);

CREATE TABLE sessions (
    session_id TEXT PRIMARY KEY,
    state      TEXT NOT NULL,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE feedback (
    order_id   INTEGER PRIMARY KEY,
    rating     INTEGER NOT NULL,
    comment    TEXT DEFAULT '',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (order_id) REFERENCES orders(id)
);

CREATE TABLE staff (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role          TEXT NOT NULL DEFAULT 'staff',   -- owner | staff
    created_at    TEXT DEFAULT CURRENT_TIMESTAMP
);
