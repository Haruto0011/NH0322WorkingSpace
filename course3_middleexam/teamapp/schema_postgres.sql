-- サーバ(PostgreSQL)用のテーブル定義
-- サーバに ssh して psql を起動し、このファイルの中身を貼り付けて実行する
--   例: psql -d s0000001 -f schema_postgres.sql

create table if not exists users (
  uid        serial primary key,
  uname      text not null,
  email      text not null unique,
  pw         text not null,                   -- ハッシュ化したパスワード
  role       text not null default 'member',  -- 'admin'(管理者) / 'member'
  number     integer,                         -- 背番号
  position   text,                            -- GK / DF / MF / FW
  created_at timestamp default current_timestamp
);

create table if not exists events (
  eid        serial primary key,
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
