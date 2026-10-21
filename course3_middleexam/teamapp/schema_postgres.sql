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
  created_by integer references users(uid),
  cancelled  integer not null default 0,    -- 1 なら中止
  season     text,                          -- '2026' など。スタッツの集計単位
  competition text                          -- '東京都リーグ' など（試合のときだけ）
);

-- 出欠：1人1予定につき1行（eid, uid の組み合わせがキー）
create table if not exists attendance (
  eid        integer not null references events(eid),
  uid        integer not null references users(uid),
  status     text not null,                   -- 'yes'(出席) / 'no'(欠席)。未回答は行がない
  comment    text,
  updated_at timestamp default current_timestamp,
  primary key (eid, uid)
);

-- 試合結果（1試合につき1行。前半/後半のスコア、PK戦、MVP）
create table if not exists match_results (
  eid        integer primary key references events(eid),
  our_1h     integer not null default 0,    -- 自チーム 前半
  our_2h     integer not null default 0,    -- 自チーム 後半
  opp_1h     integer not null default 0,    -- 相手 前半
  opp_2h     integer not null default 0,    -- 相手 後半
  our_pk     integer,                       -- PK戦（なければ NULL）
  opp_pk     integer,
  mvp_uid    integer references users(uid),
  memo       text,
  updated_at timestamp default current_timestamp
);

-- 得点（1ゴール1行。相手の得点も side='opp' で記録する）
create table if not exists goals (
  gid        serial primary key,
  eid        integer not null references events(eid),
  side       text not null,                 -- 'our' / 'opp'
  scorer_uid integer references users(uid), -- 得点者（side='our' のとき）
  assist_uid integer references users(uid), -- アシスト（任意）
  half       integer not null default 1,    -- 1=前半 / 2=後半
  minute     integer,                       -- その半分の中での分（任意）
  note       text                           -- 'PK' 'オウンゴール' など
);
