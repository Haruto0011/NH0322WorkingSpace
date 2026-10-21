"""
DBアクセスをここに集約する。
app.py 側は db.query(...) / db.execute(...) だけを使い、
SQLite か PostgreSQL かは config.DB_KIND を見てこのファイルが吸収する。

・プレースホルダは %s で統一して書く（psycopg2 の書き方）。SQLite のときは ? に置き換える
・取り出した行は row["列名"] で参照できる（テンプレートでは row.列名 でも可）
"""
import sqlite3

from flask import g

import config


def convert(sql):
    """%s プレースホルダを、SQLite のときだけ ? に置き換える"""
    if config.DB_KIND == "sqlite":
        return sql.replace("%s", "?")
    return sql


def get_conn():
    """新しいDB接続を作って返す（seed.py など Flask の外からも使う）"""
    if config.DB_KIND == "sqlite":
        conn = sqlite3.connect(config.SQLITE_PATH)
        conn.row_factory = sqlite3.Row          # row["列名"] で取れるようにする
        conn.execute("pragma foreign_keys = on")  # 外部キー制約を有効にする（SQLiteは初期OFF）
        return conn

    import psycopg2
    import psycopg2.extras
    # RealDictCursor: 行を辞書で返す（row["列名"] で取れる）
    return psycopg2.connect(config.POSTGRES_DSN, cursor_factory=psycopg2.extras.RealDictCursor)


def get_db():
    """1リクエストにつき1接続を使い回す"""
    if "db" not in g:
        g.db = get_conn()
    return g.db


def close_db(e=None):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def init_app(app):
    # リクエストが終わったら接続を閉じる
    app.teardown_appcontext(close_db)


def query(sql, params=(), one=False):
    """SELECT 用。one=True なら最初の1行（なければ None）を返す"""
    cur = get_db().cursor()
    cur.execute(convert(sql), params)
    rows = cur.fetchall()
    cur.close()
    if one:
        return rows[0] if rows else None
    return rows


def execute(sql, params=()):
    """INSERT / UPDATE / DELETE 用。実行後に commit する"""
    conn = get_db()
    cur = conn.cursor()
    cur.execute(convert(sql), params)
    conn.commit()
    cur.close()
