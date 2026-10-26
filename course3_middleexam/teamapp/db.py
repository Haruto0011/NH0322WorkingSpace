"""
Thin database layer that hides the SQLite / PostgreSQL difference.

Write SQL with ``%s`` placeholders (psycopg2 style); on SQLite they are
rewritten to ``?``. Rows support ``row["column"]`` access on both engines.
One connection is opened per request and closed on teardown.
"""
import sqlite3

from flask import g

import config


def convert(sql):
    return sql.replace("%s", "?") if config.DB_KIND == "sqlite" else sql


def get_conn():
    """Open a new connection (also used by CLI scripts outside a request)."""
    if config.DB_KIND == "sqlite":
        conn = sqlite3.connect(config.SQLITE_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute("pragma foreign_keys = on")
        return conn

    import psycopg2
    import psycopg2.extras
    return psycopg2.connect(config.POSTGRES_DSN, cursor_factory=psycopg2.extras.RealDictCursor)


def get_db():
    if "db" not in g:
        g.db = get_conn()
    return g.db


def close_db(e=None):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def init_app(app):
    app.teardown_appcontext(close_db)


def query(sql, params=(), one=False):
    """Run a SELECT. Returns a list of rows, or the first row / None if ``one``."""
    cur = get_db().cursor()
    cur.execute(convert(sql), params)
    rows = cur.fetchall()
    cur.close()
    if one:
        return rows[0] if rows else None
    return rows


def execute(sql, params=()):
    """Run an INSERT / UPDATE / DELETE and commit."""
    conn = get_db()
    cur = conn.cursor()
    cur.execute(convert(sql), params)
    conn.commit()
    cur.close()
