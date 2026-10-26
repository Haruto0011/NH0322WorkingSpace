"""
Create or upgrade the database schema. Safe to run repeatedly.

    python init_db.py

Tables are created from schema_<engine>.sql (``create table if not exists``);
MIGRATIONS below add columns introduced after the initial release and are
skipped automatically once applied.
"""
import os

import config
import db

MIGRATIONS = [
    ("events.cancelled", "alter table events add column cancelled integer not null default 0"),
    ("attendance: drop 'maybe'", "update attendance set status = 'no' where status not in ('yes', 'no')"),
    ("events.season", "alter table events add column season text"),
    ("events.competition", "alter table events add column competition text"),
    ("events.season backfill", f"update events set season = '{config.CURRENT_SEASON}' where season is null"),
    ("users.height_cm", "alter table users add column height_cm integer"),
    ("users.weight_kg", "alter table users add column weight_kg integer"),
    ("users.birthdate", "alter table users add column birthdate date"),
    ("users.foot", "alter table users add column foot text"),
    ("users.intro", "alter table users add column intro text"),
    ("users.captain", "alter table users add column captain integer not null default 0"),
]

schema_file = "schema_sqlite.sql" if config.DB_KIND == "sqlite" else "schema_postgres.sql"
with open(os.path.join(config.BASE_DIR, schema_file), encoding="utf-8") as f:
    schema = f.read()

conn = db.get_conn()
cur = conn.cursor()

if config.DB_KIND == "sqlite":
    cur.executescript(schema)
else:
    cur.execute(schema)
conn.commit()
print(f"schema applied: {schema_file} (DB_KIND={config.DB_KIND})")

for name, sql in MIGRATIONS:
    try:
        cur.execute(sql)
        conn.commit()
        print(f"  applied : {name}")
    except Exception:
        conn.rollback()
        print(f"  skipped : {name}")

cur.close()
conn.close()
