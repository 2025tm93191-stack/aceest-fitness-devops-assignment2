"""SQLite helpers. The schema follows the tables in ACEest v3.2.4."""

import sqlite3

from flask import current_app, g

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    username TEXT PRIMARY KEY,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS clients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    age INTEGER,
    height REAL,
    weight REAL,
    program TEXT,
    calories INTEGER,
    target_weight REAL,
    target_adherence INTEGER,
    generated_plan TEXT,
    membership_status TEXT DEFAULT 'Active',
    membership_end TEXT
);
CREATE TABLE IF NOT EXISTS progress (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_name TEXT NOT NULL,
    week TEXT NOT NULL,
    adherence INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS workouts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_name TEXT NOT NULL,
    date TEXT NOT NULL,
    workout_type TEXT NOT NULL,
    duration_min INTEGER NOT NULL,
    notes TEXT
);
CREATE TABLE IF NOT EXISTS exercises (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workout_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    sets INTEGER NOT NULL,
    reps INTEGER NOT NULL,
    weight REAL
);
CREATE TABLE IF NOT EXISTS metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_name TEXT NOT NULL,
    date TEXT NOT NULL,
    weight REAL NOT NULL,
    waist REAL,
    bodyfat REAL
);
"""

# Columns added to existing tables after v1.x. A database created by an older release
# gets them through ALTER TABLE, because CREATE TABLE IF NOT EXISTS leaves old tables alone.
ADDED_COLUMNS = {
    "clients": {"target_weight": "REAL", "target_adherence": "INTEGER", "generated_plan": "TEXT"},
}


def connect(path):
    conn = sqlite3.connect(path, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def get_db():
    if "db" not in g:
        g.db = connect(current_app.config["DATABASE"])
    return g.db


def close_db(_exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def migrate(conn):
    for table, columns in ADDED_COLUMNS.items():
        existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
        for column, sql_type in columns.items():
            if column in existing:
                continue
            try:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {sql_type}")
            except sqlite3.OperationalError as exc:
                # Another worker or pod sharing the database added it first.
                if "duplicate column" not in str(exc):
                    raise
    conn.commit()


def init_db():
    conn = get_db()
    conn.executescript(SCHEMA)
    migrate(conn)


def client_exists(conn, name):
    return conn.execute("SELECT 1 FROM clients WHERE name = ?", (name,)).fetchone() is not None
