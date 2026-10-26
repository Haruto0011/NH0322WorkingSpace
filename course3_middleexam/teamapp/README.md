# MUDS FC — Team Management App

A mobile-first web application for running a football club: schedule and
attendance, match results and goal records, player and team statistics,
posts, lineups and a photo album.

Built with Flask, Jinja2 and Bootstrap 5. SQLite in development,
PostgreSQL in production, with a single SQL dialect shared by both.

## Features

| Area | Details |
| --- | --- |
| Events | Practice / match / other, list and month calendar, weekly repeat creation, cancel |
| Attendance | One-tap yes / no with comment, per-event tabs (attending / absent / unanswered), pending reminder |
| Matches | Half-time and full-time score, penalty shoot-out, goals with scorer / assist / minute, MVP, memo |
| Lineups | Starters and substitutes per match, pre-sorted by attendance |
| Stats | Player rankings (goals, assists, MVP, attendance rate, appearances) by season / competition / all-time; team W-D-L and goals; per-player page |
| Community | Posts with comments and pinning, photo album per event |
| Members | Profiles (number, position, height, weight, birthdate, preferred foot), captain mark, admin editing and role management |
| App shell | Bottom tab bar, add-to-home-screen icons and manifest, team color from one setting |

## Quick start

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python init_db.py      # create tables
python seed.py         # optional demo data
python app.py          # http://127.0.0.1:5050
```

Demo accounts (password `pass1234`): `admin@example.com` (admin),
`tanaka@example.com` and other sample players. The owner account from
`config.py` is also created as an admin.

Without demo data, the first registered user becomes the administrator.
Use `python make_admin.py <email>` to promote others.

## Configuration

All settings live in `config.py`:

- `TEAM_NAME`, `TEAM_COLOR`, `CURRENT_SEASON`
- `DEMO_MODE` — when `True`, anonymous visitors act as `DEMO_USER_EMAIL`
  and the login button signs in `OWNER_EMAIL` directly without a password
  form. Set `False` for real use.
- `OWNER_NAME`, `OWNER_EMAIL`, `OWNER_PASSWORD`
- `SECRET_KEY`, `FORCE_HTTPS`
- `DB_KIND` (`sqlite` | `postgres`), `SQLITE_PATH`, `POSTGRES_DSN`
- `DEV_PORT`

Run `python make_icons.py` after changing `TEAM_COLOR` to regenerate icons.

## Project layout

```
app.py               routes and view logic
db.py                database layer (SQLite / PostgreSQL)
config.py            settings
init_db.py           schema creation and migrations
seed.py              demo data
make_admin.py        promote a user to admin
make_icons.py        icon generation
schema_sqlite.sql    schema (development)
schema_postgres.sql  schema (production)
flask.wsgi           mod_wsgi entry point
templates/           Jinja2 templates (layout, partials, pages)
static/css           Bootstrap and project styles
static/js            Bootstrap bundle
static/icons         favicon and PWA icons
static/uploads/      uploaded photos, one folder per event (not in git)
```

## Deployment (mod_wsgi)

1. In `config.py` set `DB_KIND = "postgres"`, `POSTGRES_DSN`, `FORCE_HTTPS = True`,
   a new `SECRET_KEY` and `OWNER_PASSWORD`; set `DEMO_MODE = False` for real use.
2. `pip install flask psycopg2-binary pillow`
3. `python init_db.py` (and `python seed.py` for demo data)
4. Upload the project directory and register `flask.wsgi` with the server.
5. Make `static/uploads/` writable by the web server if photo uploads are used.

## Security notes

- Passwords are stored as PBKDF2-SHA256 hashes.
- All SQL uses bound parameters.
- Uploaded files are renamed to random tokens and restricted to image types;
  large images are downscaled server-side.
- Admin-only actions are enforced on the server, not only hidden in the UI.
