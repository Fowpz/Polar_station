"""Подключение к SQLite и схема БД. Часть ограничений дублируется в CHECK."""
import sqlite3
from contextlib import contextmanager

SCHEMA = """
CREATE TABLE IF NOT EXISTS shifts(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    CHECK (end_date > start_date)
);
CREATE TABLE IF NOT EXISTS employees(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name TEXT NOT NULL,
    specialty TEXT NOT NULL,
    qualification INTEGER NOT NULL CHECK (qualification BETWEEN 1 AND 5),
    arrival_date TEXT NOT NULL,
    health TEXT NOT NULL,
    shift_id INTEGER NOT NULL REFERENCES shifts(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS users(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL,
    employee_id INTEGER REFERENCES employees(id) ON DELETE SET NULL
);
CREATE TABLE IF NOT EXISTS instruments(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    kind_code TEXT NOT NULL,
    last_calibration TEXT NOT NULL,
    interval_days INTEGER NOT NULL CHECK (interval_days > 0)
);
CREATE TABLE IF NOT EXISTS measurements(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind_code TEXT NOT NULL,
    value REAL NOT NULL,
    measured_at TEXT NOT NULL,
    instrument_id INTEGER NOT NULL REFERENCES instruments(id),
    operator_id INTEGER NOT NULL REFERENCES employees(id)
);
CREATE TABLE IF NOT EXISTS resources(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    category TEXT NOT NULL,
    unit TEXT NOT NULL,
    quantity REAL NOT NULL CHECK (quantity >= 0),
    min_norm REAL NOT NULL CHECK (min_norm >= 0)
);
CREATE TABLE IF NOT EXISTS resource_movements(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    resource_id INTEGER NOT NULL REFERENCES resources(id),
    delta REAL NOT NULL,
    at TEXT NOT NULL,
    username TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS supply_requests(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    resource_id INTEGER NOT NULL REFERENCES resources(id),
    quantity REAL NOT NULL CHECK (quantity > 0),
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    decided_at TEXT
);
CREATE TABLE IF NOT EXISTS generators(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    motohours REAL NOT NULL CHECK (motohours >= 0),
    last_service_mh REAL NOT NULL CHECK (last_service_mh >= 0)
);
CREATE TABLE IF NOT EXISTS incidents(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    description TEXT NOT NULL,
    measures_taken TEXT NOT NULL
);
"""


class Database:
    def __init__(self, path: str = ":memory:"):
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.executescript(SCHEMA)

    @contextmanager
    def tx(self):
        """Транзакция: commit при успехе, rollback при любой ошибке."""
        try:
            yield self.conn
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise

    def close(self):
        self.conn.close()
