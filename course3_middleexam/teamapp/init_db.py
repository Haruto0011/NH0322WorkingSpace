"""
テーブルを作る / 更新する:  python init_db.py
  ・初回: schema_*.sql のとおりにテーブルを作る
  ・2回目以降: 既にあるテーブルはそのまま、MIGRATIONS にある列の追加だけを行う
    （データを消さずに構造を変えるための仕組み。何度実行しても安全）
config.DB_KIND に応じて schema_sqlite.sql / schema_postgres.sql を読み込む
"""
import os

import config
import db

# 後から追加したテーブル変更はここに足していく（上から順に実行、適用済みならスキップ）
MIGRATIONS = [
    ("events に cancelled 列を追加", "alter table events add column cancelled integer not null default 0"),
    ("出欠の '未定' を廃止（欠席扱いに）", "update attendance set status = 'no' where status not in ('yes', 'no')"),
    ("events に season 列を追加", "alter table events add column season text"),
    ("events に competition 列を追加", "alter table events add column competition text"),
    ("season が空の予定に今のシーズンを入れる",
     f"update events set season = '{config.CURRENT_SEASON}' where season is null"),
]

if config.DB_KIND == "sqlite":
    schema_file = "schema_sqlite.sql"
else:
    schema_file = "schema_postgres.sql"

path = os.path.join(config.BASE_DIR, schema_file)
with open(path, encoding="utf-8") as f:
    schema = f.read()

conn = db.get_conn()
cur = conn.cursor()

# 1) テーブル作成（create table if not exists なので、あるものは触らない）
if config.DB_KIND == "sqlite":
    cur.executescript(schema)  # SQLite は複数文を一度に実行するのに executescript を使う
else:
    cur.execute(schema)
conn.commit()
print(f"OK: {schema_file} を実行しました（DB_KIND = {config.DB_KIND}）")

# 2) 列の追加など（既に適用済みならエラーになるので、それはスキップ）
for desc, sql in MIGRATIONS:
    try:
        cur.execute(sql)
        conn.commit()
        print(f"  適用: {desc}")
    except Exception:
        conn.rollback()
        print(f"  スキップ（適用済み）: {desc}")

cur.close()
conn.close()
