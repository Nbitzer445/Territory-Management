-- BRM Territory Hub database schema
-- All data lives in a single local SQLite file (data/territory.db).
-- Nothing here is ever synced anywhere.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    company_type TEXT,          -- Contractor / Distributor / End Customer / Manufacturers Rep / Principal / etc
    class TEXT,
    category TEXT,
    street TEXT,
    city TEXT,
    state TEXT,
    zip TEXT,
    market TEXT,                 -- Lincoln / Omaha / Norfolk / Columbus / Fremont / Sioux City / NW Iowa / Other
    phone TEXT,
    website TEXT,
    status TEXT,
    notes TEXT,
    source TEXT DEFAULT 'derived',   -- companies_import | derived | manual
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS contacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    role TEXT,
    phone TEXT,
    email TEXT,
    notes TEXT,
    source TEXT DEFAULT 'manual',   -- journal_import | manual
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS brands (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    category TEXT,          -- e.g. plumbing / hvac / water-heaters / admin
    notes TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS calls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    contact_id INTEGER REFERENCES contacts(id) ON DELETE SET NULL,
    call_date TEXT NOT NULL,        -- ISO YYYY-MM-DD
    report_type TEXT,               -- Distributor Call Report / Contractor Call Report / Email / Phone / Job Site Visit
    subject TEXT,
    brand_id INTEGER REFERENCES brands(id) ON DELETE SET NULL,
    attendees TEXT,
    notes TEXT,
    followup_date TEXT,
    followup_notes TEXT,
    source TEXT DEFAULT 'manual',   -- journal_import | manual
    import_key TEXT,                -- stable de-dup key for re-imports
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_calls_import_key ON calls(import_key) WHERE import_key IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_calls_account ON calls(account_id);
CREATE INDEX IF NOT EXISTS idx_calls_date ON calls(call_date);

CREATE TABLE IF NOT EXISTS followups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    contact_id INTEGER REFERENCES contacts(id) ON DELETE SET NULL,
    call_id INTEGER REFERENCES calls(id) ON DELETE SET NULL,
    description TEXT,
    due_date TEXT,
    status TEXT DEFAULT 'open',     -- open | done
    source TEXT DEFAULT 'manual',   -- auto | manual
    created_at TEXT DEFAULT (datetime('now')),
    completed_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_followups_due ON followups(due_date);
CREATE INDEX IF NOT EXISTS idx_followups_status ON followups(status);

CREATE TABLE IF NOT EXISTS import_batches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_type TEXT,        -- companies | journal | sales
    filename TEXT,
    imported_at TEXT DEFAULT (datetime('now')),
    summary_json TEXT
);

CREATE TABLE IF NOT EXISTS sales_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    brand_id INTEGER NOT NULL REFERENCES brands(id) ON DELETE CASCADE,
    current_label TEXT,     -- e.g. '6/30/26 YTD'
    prior_label TEXT,       -- e.g. '6/30/25 YTD'
    current_ytd REAL,
    prior_ytd REAL,
    variance REAL,
    import_batch_id INTEGER REFERENCES import_batches(id),
    imported_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_sales_account ON sales_snapshots(account_id);
CREATE INDEX IF NOT EXISTS idx_sales_brand ON sales_snapshots(brand_id);
CREATE INDEX IF NOT EXISTS idx_sales_batch ON sales_snapshots(import_batch_id);

CREATE TABLE IF NOT EXISTS news_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    url TEXT,
    source TEXT,
    published_at TEXT,
    summary TEXT,
    category TEXT,           -- commodity | manufacturer | market | demand | manual
    query_tag TEXT,          -- which brand/keyword produced this (for live-fetched items)
    manual INTEGER DEFAULT 0,
    saved INTEGER DEFAULT 0,
    fetched_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_news_fetched ON news_items(fetched_at);

CREATE TABLE IF NOT EXISTS news_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    news_id INTEGER NOT NULL REFERENCES news_items(id) ON DELETE CASCADE,
    account_id INTEGER REFERENCES accounts(id) ON DELETE CASCADE,
    brand_id INTEGER REFERENCES brands(id) ON DELETE CASCADE
);
