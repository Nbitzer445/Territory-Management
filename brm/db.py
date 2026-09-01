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


def init_db():
    conn = get_connection()
    with open(SCHEMA_PATH, "r") as f:
        conn.executescript(f.read())
    conn.commit()
    migrate(conn)
    conn.close()


def dict_from_row(row):
    return dict(row) if row is not None else None


def dicts_from_rows(rows):
    return [dict(r) for r in rows]
