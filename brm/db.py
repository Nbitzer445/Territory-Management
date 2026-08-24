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


def init_db():
    conn = get_connection()
    with open(SCHEMA_PATH, "r") as f:
        conn.executescript(f.read())
    conn.commit()
    conn.close()


def dict_from_row(row):
    return dict(row) if row is not None else None


def dicts_from_rows(rows):
    return [dict(r) for r in rows]
