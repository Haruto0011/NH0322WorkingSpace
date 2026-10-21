-- 手元(SQLite)用のテーブル定義。python init_db.py で実行される
-- サーバ(PostgreSQL)用は schema_postgres.sql（内容は同じ、型名だけ違う）

create table if not exists users (
  uid        integer primary key autoincrement,
  uname      text not null,
  email      text not null unique,
  pw         text not null,                   -- ハッシュ化したパスワード
  role       text not null default 'member',  -- 'admin'(管理者) / 'member'
  number     integer,                         -- 背番号
  position   text,                            -- GK / DF / MF / FW
  created_at timestamp default current_timestamp
);

create table if not exists events (
  eid        integer primary key autoincrement,
  etype      text not null,                   -- 'practice' / 'match' / 'other'
  title      text not null,
  event_date date not null,
  start_time time,
  end_time   time,
  place      text,
  opponent   text,                            -- 試合のときだけ
  note       text,
  created_by integer references users(uid)
);

-- 出欠：1人1予定につき1行（eid, uid の組み合わせがキー）
create table if not exists attendance (
  eid        integer not null references events(eid),
  uid        integer not null references users(uid),
  status     text not null,                   -- 'yes' / 'maybe' / 'no'
  comment    text,
  updated_at timestamp default current_timestamp,
  primary key (eid, uid)
);
