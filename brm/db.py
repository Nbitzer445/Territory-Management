"""SQLite connection + schema bootstrap for BRM Territory Hub.

Everything lives in one local file: data/territory.db. No network, no cloud.
"""
import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "territory.db"
SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


def get_connection():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# Columns added after the first release. Each entry is applied only if the
# column is missing, so an existing database with real data in it upgrades
# in place without losing anything.
MIGRATIONS = [
    ("accounts", "tier", "TEXT"),
    ("accounts", "cadence_days", "INTEGER"),
    ("accounts", "group_id", "INTEGER"),
]


def migrate(conn):
    """Add any columns introduced after a user's database was first created."""
    applied = []
    for table, column, coltype in MIGRATIONS:
        existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
        if not existing:
            continue  # table doesn't exist yet; schema.sql will create it
        if column not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {coltype}")
            applied.append(f"{table}.{column}")
    if applied:
        conn.commit()
    return applied


def _meta_get(conn, key):
    row = conn.execute("SELECT value FROM app_meta WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else None


def _meta_set(conn, key, value):
    conn.execute("INSERT OR REPLACE INTO app_meta (key, value) VALUES (?, ?)", (key, value))


def seed_kelly_group(conn):
    """Create the Kelly Group once.

    Kelly's branches share POs -- product is bought on one account and
    transferred to another -- so only the combined number is meaningful. This
    runs a single time and records that it did, so it won't come back if the
    group is later renamed, changed, or deliberately removed.
    """
    if _meta_get(conn, "kelly_group_seeded"):
        return None
    members = conn.execute(
        "SELECT id FROM accounts WHERE name LIKE 'Kelly Supply%'"
    ).fetchall()
    if not members:
        return None  # nothing imported yet; try again on a later start

    conn.execute(
        "INSERT OR IGNORE INTO account_groups (name, notes) VALUES (?, ?)",
        ("Kelly Group",
         "Branches share POs -- product is often bought on one account and transferred to "
         "another, so only the combined number is meaningful."),
    )
    gid = conn.execute("SELECT id FROM account_groups WHERE name = 'Kelly Group'").fetchone()["id"]
    conn.execute(
        "UPDATE accounts SET group_id = ? WHERE name LIKE 'Kelly Supply%' AND group_id IS NULL",
        (gid,),
    )
    _meta_set(conn, "kelly_group_seeded", "1")
    conn.commit()
    return gid


def init_db():
    conn = get_connection()
    with open(SCHEMA_PATH, "r") as f:
        conn.executescript(f.read())
    conn.commit()
    migrate(conn)
    try:
        seed_kelly_group(conn)
    except Exception:
        pass  # never block startup on a convenience seed
    conn.close()


def dict_from_row(row):
    return dict(row) if row is not None else None


def dicts_from_rows(rows):
    return [dict(r) for r in rows]
