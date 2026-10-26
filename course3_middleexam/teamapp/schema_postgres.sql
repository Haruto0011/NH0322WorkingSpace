-- Schema for PostgreSQL (production). Keep in sync with schema_sqlite.sql.

create table if not exists users (
  uid        serial primary key,
  uname      text not null,
  email      text not null unique,
  pw         text not null,                   -- password hash
  role       text not null default 'member',  -- 'admin' | 'member'
  number     integer,                         -- shirt number
  position   text,                            -- GK | DF | MF | FW
  height_cm  integer,
  weight_kg  integer,
  birthdate  date,
  foot       text,                            -- preferred foot
  intro      text,
  captain    integer not null default 0,
  vice_captain integer not null default 0,
  status     text not null default 'active', -- 'active' | 'ob' (alumni)
  created_at timestamp default current_timestamp
);

create table if not exists events (
  eid        serial primary key,
  etype      text not null,                   -- 'practice' | 'match' | 'other'
  title      text not null,
  event_date date not null,
  start_time time,
  end_time   time,
  place      text,
  opponent   text,                            -- matches only
  note       text,
  created_by integer references users(uid),
  cancelled  integer not null default 0,
  season     text,                            -- e.g. '2026'; stats are grouped by season
  competition text                            -- e.g. league / cup name (matches only)
);

-- One row per member per event; no row means unanswered.
create table if not exists attendance (
  eid        integer not null references events(eid),
  uid        integer not null references users(uid),
  status     text not null,                   -- 'yes' | 'no'
  comment    text,
  updated_at timestamp default current_timestamp,
  primary key (eid, uid)
);

create table if not exists match_results (
  eid        integer primary key references events(eid),
  our_1h     integer not null default 0,      -- goals for, first half
  our_2h     integer not null default 0,
  opp_1h     integer not null default 0,      -- goals against, first half
  opp_2h     integer not null default 0,
  our_pk     integer,                         -- penalty shoot-out (null if none)
  opp_pk     integer,
  mvp_uid    integer references users(uid),
  memo       text,
  updated_at timestamp default current_timestamp
);

-- One row per goal, for both sides.
create table if not exists goals (
  gid        serial primary key,
  eid        integer not null references events(eid),
  side       text not null,                   -- 'our' | 'opp'
  scorer_uid integer references users(uid),   -- our goals only
  assist_uid integer references users(uid),
  half       integer not null default 1,      -- 1 | 2
  minute     integer,
  note       text                             -- e.g. 'PK', 'OG'
);

create table if not exists posts (
  pid        serial primary key,
  uid        integer references users(uid),
  title      text,
  body       text not null,
  pinned     integer not null default 0,
  created_at timestamp not null
);

create table if not exists comments (
  cid        serial primary key,
  pid        integer not null references posts(pid),
  uid        integer references users(uid),
  body       text not null,
  created_at timestamp not null
);

create table if not exists lineups (
  eid        integer not null references events(eid),
  uid        integer not null references users(uid),
  role       text not null,                   -- 'starter' | 'sub'
  primary key (eid, uid)
);

-- Files are stored under static/uploads/<eid>/.
create table if not exists photos (
  phid       serial primary key,
  eid        integer not null references events(eid),
  uid        integer references users(uid),
  filename   text not null,
  caption    text,
  created_at timestamp not null
);
