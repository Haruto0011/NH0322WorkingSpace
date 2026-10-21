"""
テーブルを作る。最初に1回だけ実行する:  python init_db.py
config.DB_KIND に応じて schema_sqlite.sql / schema_postgres.sql を読み込む
"""
import os

import config
import db

if config.DB_KIND == "sqlite":
    schema_file = "schema_sqlite.sql"
else:
    schema_file = "schema_postgres.sql"

path = os.path.join(config.BASE_DIR, schema_file)
with open(path, encoding="utf-8") as f:
    schema = f.read()

conn = db.get_conn()
if config.DB_KIND == "sqlite":
    conn.executescript(schema)  # SQLite は複数文を一度に実行するのに executescript を使う
else:
    cur = conn.cursor()
    cur.execute(schema)
    cur.close()
conn.commit()
conn.close()

print(f"OK: {schema_file} を実行しました（DB_KIND = {config.DB_KIND}）")
