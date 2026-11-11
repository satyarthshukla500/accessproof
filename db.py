import os
import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS orders(
  id TEXT PRIMARY KEY, capture_id TEXT, payer_email TEXT, amount TEXT, currency TEXT,
  product TEXT, created_at TEXT, source TEXT DEFAULT 'real');
CREATE TABLE IF NOT EXISTS ledger(
  id INTEGER PRIMARY KEY AUTOINCREMENT, order_id TEXT, event TEXT, ts TEXT, ip TEXT, ua TEXT,
  detail TEXT, prev_hash TEXT, hash TEXT);
CREATE INDEX IF NOT EXISTS ledger_order ON ledger(order_id);
CREATE TABLE IF NOT EXISTS help_requests(
  id INTEGER PRIMARY KEY AUTOINCREMENT, order_id TEXT, message TEXT, intent TEXT, reply TEXT,
  action TEXT, cited TEXT, flagged INTEGER DEFAULT 0, outcome TEXT DEFAULT 'open',
  created_at TEXT, source TEXT DEFAULT 'real');
CREATE TABLE IF NOT EXISTS refund_requests(
  id INTEGER PRIMARY KEY AUTOINCREMENT, order_id TEXT, help_id INTEGER, amount TEXT,
  status TEXT DEFAULT 'pending', paypal_refund_id TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS disputes(
  id TEXT PRIMARY KEY, order_id TEXT, capture_id TEXT, reason TEXT, status TEXT, stage TEXT,
  amount TEXT, currency TEXT, raw TEXT, covered INTEGER, recommendation TEXT, pack TEXT,
  last_result TEXT, source TEXT DEFAULT 'paypal', created_at TEXT);
"""


def path():
    return os.environ.get("DB_PATH", "accessproof.db")


def connect():
    con = sqlite3.connect(path())
    con.row_factory = sqlite3.Row
    return con


def init():
    with connect() as con:
        con.executescript(SCHEMA)


def query(sql, args=()):
    with connect() as con:
        return [dict(r) for r in con.execute(sql, args)]


def one(sql, args=()):
    rows = query(sql, args)
    return rows[0] if rows else None


def changed(sql, args=()):
    """Runs a write and returns how many rows it changed."""
    with connect() as con:
        return con.execute(sql, args).rowcount


def run(sql, args=()):
    with connect() as con:
        return con.execute(sql, args).lastrowid
