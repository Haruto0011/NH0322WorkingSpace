"""
Team management web app for a football club.

Flask + SQLite (development) / PostgreSQL (production), server-rendered with
Jinja2 and Bootstrap. All database access goes through ``db.py``; SQL is
written with ``%s`` placeholders so the same statements run on both engines.

Sections:
    - app setup, helpers, template filters
    - authentication
    - home, events, attendance
    - match results, goals, scores
    - stats
    - posts and comments
    - lineups
    - photos and album
    - members and profiles
    - error handlers, web manifest
"""
import calendar
import math
import os
import secrets
from collections import defaultdict
from datetime import date, datetime, timedelta
from functools import wraps

from flask import (Flask, abort, flash, g, jsonify, redirect, render_template,
                   request, session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

import config
import db

app = Flask(__name__)
app.config["SECRET_KEY"] = config.SECRET_KEY
app.config["MAX_CONTENT_LENGTH"] = 40 * 1024 * 1024  # upload limit per request
app.permanent_session_lifetime = timedelta(days=30)
db.init_app(app)

# Display labels for enumerated values (UI language is Japanese).
ETYPES = {"practice": "練習", "match": "試合", "other": "その他"}
POSITIONS = ["GK", "DF", "MF", "FW"]
FEET = ["右", "左", "両"]
STATUSES = {"yes": "出席", "no": "欠席"}  # no row = unanswered
HALVES = {1: "前半", 2: "後半"}
LINEUP_ROLES = {"starter": "先発", "sub": "控え"}
OUTCOMES = {"win": "勝ち", "draw": "引き分け", "loss": "負け"}
PHOTO_EXTS = {"jpg", "jpeg", "png", "gif", "webp"}
WEEKDAYS = "月火水木金土日"

UPLOAD_DIR = os.path.join(config.BASE_DIR, "static", "uploads")


# ---------------------------------------------------------------------------
# Request setup, access control, template helpers
# ---------------------------------------------------------------------------

@app.before_request
def load_current_user():
    if config.FORCE_HTTPS and not request.is_secure:
        return redirect(request.url.replace("http://", "https://", 1))

    g.user = None
    g.demo = False
    if session.get("uid"):
        g.user = db.query("select * from users where uid = %s", (session["uid"],), one=True)

    # Demo mode: anonymous visitors act as the configured demo user.
    if g.user is None and config.DEMO_MODE:
        g.user = db.query("select * from users where email = %s", (config.DEMO_USER_EMAIL,), one=True)
        g.demo = g.user is not None


@app.context_processor
def inject_globals():
    return {
        "team_name": config.TEAM_NAME,
        "team_color": config.TEAM_COLOR,
        "ETYPES": ETYPES,
        "POSITIONS": POSITIONS,
        "FEET": FEET,
        "STATUSES": STATUSES,
        "HALVES": HALVES,
        "OUTCOMES": OUTCOMES,
        "LINEUP_ROLES": LINEUP_ROLES,
    }


def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if g.user is None:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper


def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if g.user is None:
            return redirect(url_for("login"))
        if g.user["role"] != "admin":
            flash("この操作は管理者のみ行えます。", "warning")
            return redirect(url_for("index"))
        return f(*args, **kwargs)
    return wrapper


def _as_date(v):
    """SQLite returns ISO strings, PostgreSQL returns date objects."""
    return date.fromisoformat(v) if isinstance(v, str) else v


@app.template_filter("jdate")
def jdate(v):
    """2026-10-25 -> 10/25(土)"""
    if not v:
        return ""
    v = _as_date(v)
    return f"{v.month}/{v.day}({WEEKDAYS[v.weekday()]})"


@app.template_filter("jfulldate")
def jfulldate(v):
    """2004-05-17 -> 2004年5月17日"""
    if not v:
        return ""
    v = _as_date(v)
    return f"{v.year}年{v.month}月{v.day}日"


@app.template_filter("jtime")
def jtime(v):
    """19:00:00 -> 19:00"""
    return str(v)[:5] if v else ""


@app.template_filter("jdatetime")
def jdatetime(v):
    """2026-10-26 22:56:00 -> 10/26(月) 22:56"""
    if not v:
        return ""
    if isinstance(v, str):
        v = datetime.fromisoformat(v[:19])
    return f"{v.month}/{v.day}({WEEKDAYS[v.weekday()]}) {v:%H:%M}"


def now_str():
    """Local timestamp for created_at columns (SQLite's current_timestamp is UTC)."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _age(birthdate):
    if not birthdate:
        return None
    birthdate = _as_date(birthdate)
    today = date.today()
    age = today.year - birthdate.year
    if (today.month, today.day) < (birthdate.month, birthdate.day):
        age -= 1
    return age


def _int_or(value, default=None):
    """Parse a non-negative integer from a form field, or return ``default``."""
    value = (value or "").strip()
    return int(value) if value.isdigit() else default


def _can_delete(owner_uid):
    return g.user["role"] == "admin" or owner_uid == g.user["uid"]


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

@app.route("/regist")
def regist():
    return render_template("regist.html", title="新規登録")


@app.route("/registing", methods=["POST"])
def registing():
    unf = request.form.get("unf", "").strip()
    emf = request.form.get("emf", "").strip().lower()
    pwf1 = request.form.get("pwf1", "")
    pwf2 = request.form.get("pwf2", "")

    if not (unf and emf and pwf1 and pwf2):
        flash("すべての項目を入力してください。", "danger")
        return redirect(url_for("regist"))
    if pwf1 != pwf2:
        flash("パスワードが一致しません。", "danger")
        return redirect(url_for("regist"))
    if db.query("select uid from users where email = %s", (emf,), one=True):
        flash("このメールアドレスは既に登録されています。", "danger")
        return redirect(url_for("regist"))

    # The first registered user becomes the administrator.
    first_user = db.query("select count(*) as c from users", one=True)["c"] == 0
    db.execute("insert into users (uname, email, pw, role) values (%s, %s, %s, %s)",
               (unf, emf, generate_password_hash(pwf1, method="pbkdf2:sha256"),
                "admin" if first_user else "member"))

    flash("登録しました。ログインしてください。", "success")
    return redirect(url_for("login"))


@app.route("/login")
def login():
    if g.user and not g.demo:
        return redirect(url_for("index"))
    # In demo mode the login button signs in the owner account directly;
    # the regular form is still available at /login?form=1.
    if config.DEMO_MODE and not request.args.get("form"):
        owner = db.query("select * from users where email = %s", (config.OWNER_EMAIL.lower(),), one=True)
        if owner:
            session.permanent = True
            session["uid"] = owner["uid"]
            flash(f"{owner['uname']} としてログインしました。", "success")
            return redirect(url_for("index"))
    return render_template("login.html", title="ログイン")


@app.route("/logingin", methods=["POST"])
def logingin():
    emf = request.form.get("emf", "").strip().lower()
    pwf = request.form.get("pwf", "")
    user = db.query("select * from users where email = %s", (emf,), one=True)
    if user is None or not check_password_hash(user["pw"], pwf):
        flash("メールアドレスまたはパスワードが違います。", "danger")
        return redirect(url_for("login"))
    session.permanent = True
    session["uid"] = user["uid"]
    return redirect(url_for("index"))


@app.route("/logout")
def logout():
    session.clear()
    flash("ログアウトしました。", "success")
    return redirect(url_for("index") if config.DEMO_MODE else url_for("login"))


# ---------------------------------------------------------------------------
# Home, events, attendance
# ---------------------------------------------------------------------------

# Event rows with attendance count and the current user's own answer.
# First bound parameter is the current user's uid.
EVENT_LIST_SQL = """
select e.*,
  (select count(*) from attendance a where a.eid = e.eid and a.status = 'yes') as yes_count,
  (select a.status from attendance a where a.eid = e.eid and a.uid = %s) as my_status
from events e
"""


@app.route("/")
@login_required
def index():
    today = date.today().isoformat()
    uid = g.user["uid"]

    events = db.query(
        EVENT_LIST_SQL + " where e.event_date >= %s order by e.event_date, e.start_time limit 5",
        (uid, today))
    pending = db.query("""
        select count(*) as c from events e
        where e.event_date >= %s and e.cancelled = 0
          and not exists (select 1 from attendance a where a.eid = e.eid and a.uid = %s)
    """, (today, uid), one=True)["c"]

    latest_list, _ = _match_list(limit=1)
    _, summary = _match_list(season=config.CURRENT_SEASON)
    member_count = db.query("select count(*) as c from users", one=True)["c"]
    latest_posts = db.query(POST_SQL + " order by p.pinned desc, p.created_at desc limit 3")

    return render_template("index.html", title="ホーム", events=events, pending=pending,
                           latest=latest_list[0] if latest_list else None,
                           summary=summary, donut=_donut(summary),
                           season=config.CURRENT_SEASON, member_count=member_count,
                           posts=latest_posts)


@app.route("/events")
@login_required
def events():
    today = date.today().isoformat()
    uid = g.user["uid"]
    upcoming = db.query(
        EVENT_LIST_SQL + " where e.event_date >= %s order by e.event_date, e.start_time",
        (uid, today))
    past = db.query(
        EVENT_LIST_SQL + " where e.event_date < %s order by e.event_date desc limit 20",
        (uid, today))
    return render_template("events.html", title="予定", upcoming=upcoming, past=past)


@app.route("/events/calendar")
@login_required
def events_calendar():
    """Month view. ``?ym=YYYY-MM`` selects the month (defaults to current)."""
    today = date.today()
    try:
        y, m = (int(x) for x in request.args.get("ym", "").split("-"))
        date(y, m, 1)
    except (ValueError, TypeError):
        y, m = today.year, today.month
    first = date(y, m, 1)
    last = date(y, m, calendar.monthrange(y, m)[1])

    rows = db.query(
        EVENT_LIST_SQL + " where e.event_date between %s and %s order by e.event_date, e.start_time",
        (g.user["uid"], first.isoformat(), last.isoformat()))
    by_day = defaultdict(list)
    for r in rows:
        by_day[int(str(r["event_date"])[8:10])].append(r)

    weeks = calendar.Calendar(firstweekday=6).monthdayscalendar(y, m)  # weeks start on Sunday
    return render_template("events_calendar.html", title=f"{y}年{m}月の予定",
                           y=y, m=m, weeks=weeks, by_day=by_day, events=rows, today=today,
                           prev_ym=(first - timedelta(days=1)).strftime("%Y-%m"),
                           next_ym=(last + timedelta(days=1)).strftime("%Y-%m"),
                           this_ym=today.strftime("%Y-%m"))


@app.route("/events/<int:eid>")
@login_required
def event_detail(eid):
    ev = db.query("""
        select e.*, u.uname as creator
        from events e
        left join users u on u.uid = e.created_by
        where e.eid = %s
    """, (eid,), one=True)
    if ev is None:
        abort(404)

    members = db.query("""
        select u.uid, u.uname, u.number, u.position, a.status, a.comment
        from users u
        left join attendance a on a.uid = u.uid and a.eid = %s
        order by coalesce(u.number, 999), u.uname
    """, (eid,))
    groups = {"yes": [], "no": [], "none": []}
    mine = None
    for m in members:
        groups[m["status"] if m["status"] in STATUSES else "none"].append(m)
        if m["uid"] == g.user["uid"]:
            mine = m
    counts = {key: len(lst) for key, lst in groups.items()}

    result = goals = score = lineup = None
    if ev["etype"] == "match":
        result = _match_result(eid)
        goals = _goals(eid)
        lineup = _lineup(eid)
        if result:
            our = result["our_1h"] + result["our_2h"]
            opp = result["opp_1h"] + result["opp_2h"]
            score = {"our": our, "opp": opp, "outcome": _outcome(our, opp)}

    return render_template("event_detail.html", title=ev["title"], ev=ev,
                           groups=groups, counts=counts, mine=mine,
                           result=result, goals=goals, score=score,
                           lineup=lineup, photos=_photos(eid))


@app.route("/events/<int:eid>/attend", methods=["POST"])
@login_required
def attend(eid):
    status = request.form.get("status")
    comment = request.form.get("comment", "").strip()
    if status not in STATUSES:
        flash("出欠を選んでください。", "danger")
        return redirect(url_for("event_detail", eid=eid))

    ev = db.query("select cancelled from events where eid = %s", (eid,), one=True)
    if ev is None:
        abort(404)
    if ev["cancelled"]:
        flash("この予定は中止になっています。", "warning")
        return redirect(url_for("event_detail", eid=eid))

    db.execute("""
        insert into attendance (eid, uid, status, comment, updated_at)
        values (%s, %s, %s, %s, current_timestamp)
        on conflict (eid, uid) do update
          set status = excluded.status,
              comment = excluded.comment,
              updated_at = current_timestamp
    """, (eid, g.user["uid"], status, comment))
    flash("出欠を回答しました。", "success")
    return redirect(url_for("event_detail", eid=eid))


def _event_from_form():
    etype = request.form.get("etype")
    return {
        "etype": etype if etype in ETYPES else "practice",
        "title": request.form.get("title", "").strip(),
        "event_date": request.form.get("event_date", ""),
        "start_time": request.form.get("start_time") or None,
        "end_time": request.form.get("end_time") or None,
        "place": request.form.get("place", "").strip(),
        "opponent": request.form.get("opponent", "").strip(),
        "note": request.form.get("note", "").strip(),
        "season": request.form.get("season", "").strip() or config.CURRENT_SEASON,
        "competition": request.form.get("competition", "").strip(),
    }


def _form_choices():
    """Previously used season and competition names, for datalist suggestions."""
    seasons = [r["season"] for r in db.query(
        "select distinct season from events where season is not null and season <> '' order by season desc")]
    if config.CURRENT_SEASON not in seasons:
        seasons.insert(0, config.CURRENT_SEASON)
    competitions = [r["competition"] for r in db.query(
        "select distinct competition from events where competition is not null and competition <> '' order by competition")]
    return {"seasons": seasons, "competitions": competitions}


@app.route("/events/new", methods=["GET", "POST"])
@admin_required
def event_new():
    if request.method == "POST":
        f = _event_from_form()
        if not f["title"] or not f["event_date"]:
            flash("タイトルと日付は必須です。", "danger")
            return render_template("event_form.html", title="予定を追加", ev=f, **_form_choices())

        # Optional weekly / biweekly repetition.
        count = 1
        if request.form.get("repeat") == "on":
            count = min(max(_int_or(request.form.get("repeat_count"), 1), 1), 30)
        interval = 14 if request.form.get("repeat_weeks") == "2" else 7
        first = date.fromisoformat(f["event_date"])

        for i in range(count):
            db.execute("""
                insert into events (etype, title, event_date, start_time, end_time,
                                    place, opponent, note, season, competition, created_by)
                values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (f["etype"], f["title"], (first + timedelta(days=interval * i)).isoformat(),
                  f["start_time"], f["end_time"], f["place"], f["opponent"], f["note"],
                  f["season"], f["competition"], g.user["uid"]))

        flash(f"{count}件の予定を追加しました。" if count > 1 else "予定を追加しました。", "success")
        return redirect(url_for("events"))
    return render_template("event_form.html", title="予定を追加", ev=None, **_form_choices())


@app.route("/events/<int:eid>/edit", methods=["GET", "POST"])
@admin_required
def event_edit(eid):
    ev = db.query("select * from events where eid = %s", (eid,), one=True)
    if ev is None:
        abort(404)
    if request.method == "POST":
        f = _event_from_form()
        if not f["title"] or not f["event_date"]:
            flash("タイトルと日付は必須です。", "danger")
            f["eid"] = eid
            return render_template("event_form.html", title="予定を編集", ev=f, **_form_choices())
        db.execute("""
            update events
               set etype = %s, title = %s, event_date = %s, start_time = %s, end_time = %s,
                   place = %s, opponent = %s, note = %s, season = %s, competition = %s
             where eid = %s
        """, (f["etype"], f["title"], f["event_date"], f["start_time"], f["end_time"],
              f["place"], f["opponent"], f["note"], f["season"], f["competition"], eid))
        flash("予定を更新しました。", "success")
        return redirect(url_for("event_detail", eid=eid))
    return render_template("event_form.html", title="予定を編集", ev=ev, **_form_choices())


@app.route("/events/<int:eid>/cancel", methods=["POST"])
@admin_required
def event_cancel(eid):
    """Toggle the cancelled flag without deleting the event."""
    ev = db.query("select cancelled from events where eid = %s", (eid,), one=True)
    if ev is None:
        abort(404)
    cancelled = 0 if ev["cancelled"] else 1
    db.execute("update events set cancelled = %s where eid = %s", (cancelled, eid))
    flash("予定を中止にしました。" if cancelled else "中止を取り消しました。", "success")
    return redirect(url_for("event_detail", eid=eid))


@app.route("/events/<int:eid>/delete", methods=["POST"])
@admin_required
def event_delete(eid):
    for table in ("attendance", "goals", "match_results", "lineups", "photos"):
        db.execute(f"delete from {table} where eid = %s", (eid,))
    db.execute("delete from events where eid = %s", (eid,))
    flash("予定を削除しました。", "success")
    return redirect(url_for("events"))


# ---------------------------------------------------------------------------
# Match results, goals, scores
# ---------------------------------------------------------------------------

def _match_result(eid):
    return db.query("""
        select r.*, u.uname as mvp
        from match_results r
        left join users u on u.uid = r.mvp_uid
        where r.eid = %s
    """, (eid,), one=True)


def _goals(eid):
    return db.query("""
        select g.*, s.uname as scorer, a.uname as assist
        from goals g
        left join users s on s.uid = g.scorer_uid
        left join users a on a.uid = g.assist_uid
        where g.eid = %s
        order by g.half, coalesce(g.minute, 999), g.gid
    """, (eid,))


def _outcome(our, opp):
    if our > opp:
        return "win"
    if our < opp:
        return "loss"
    return "draw"


def _match_list(season=None, competition=None, limit=None):
    """Matches with a recorded result, newest first, plus a W/D/L and goals summary."""
    sql = """
        select e.eid, e.title, e.event_date, e.opponent, e.competition, e.season,
               r.our_1h, r.our_2h, r.opp_1h, r.opp_2h, r.our_pk, r.opp_pk
        from events e
        join match_results r on r.eid = e.eid
        where e.etype = 'match'
    """
    params = []
    if season:
        sql += " and e.season = %s"
        params.append(season)
    if competition:
        sql += " and e.competition = %s"
        params.append(competition)
    sql += " order by e.event_date desc"
    if limit:
        sql += " limit %s"
        params.append(limit)

    matches = [dict(r) for r in db.query(sql, tuple(params))]
    summary = {"win": 0, "draw": 0, "loss": 0, "gf": 0, "ga": 0, "games": 0}
    for m in matches:
        m["our"] = m["our_1h"] + m["our_2h"]
        m["opp"] = m["opp_1h"] + m["opp_2h"]
        m["outcome"] = _outcome(m["our"], m["opp"])
        summary[m["outcome"]] += 1
        summary["gf"] += m["our"]
        summary["ga"] += m["opp"]
        summary["games"] += 1
    return matches, summary


DONUT_R = 40
DONUT_C = 2 * math.pi * DONUT_R


def _donut(summary):
    """Arc segments (stroke-dasharray / offset) for the W/D/L donut chart."""
    total = summary["games"]
    segments, offset = [], 0.0
    for key, color in (("win", "#198754"), ("draw", "#adb5bd"), ("loss", "#dc3545")):
        n = summary[key]
        if total and n:
            length = DONUT_C * n / total
            segments.append({"color": color,
                             "dash": f"{length:.2f} {DONUT_C - length:.2f}",
                             "offset": f"{-offset:.2f}"})
            offset += length
    return segments


@app.route("/events/<int:eid>/result", methods=["GET", "POST"])
@admin_required
def result_edit(eid):
    ev = db.query("select * from events where eid = %s", (eid,), one=True)
    if ev is None:
        abort(404)
    if ev["etype"] != "match":
        flash("試合以外の予定には結果を入力できません。", "warning")
        return redirect(url_for("event_detail", eid=eid))

    if request.method == "POST":
        f = request.form
        db.execute("""
            insert into match_results
                (eid, our_1h, our_2h, opp_1h, opp_2h, our_pk, opp_pk, mvp_uid, memo, updated_at)
            values (%s, %s, %s, %s, %s, %s, %s, %s, %s, current_timestamp)
            on conflict (eid) do update
              set our_1h = excluded.our_1h, our_2h = excluded.our_2h,
                  opp_1h = excluded.opp_1h, opp_2h = excluded.opp_2h,
                  our_pk = excluded.our_pk, opp_pk = excluded.opp_pk,
                  mvp_uid = excluded.mvp_uid, memo = excluded.memo,
                  updated_at = current_timestamp
        """, (eid,
              _int_or(f.get("our_1h"), 0), _int_or(f.get("our_2h"), 0),
              _int_or(f.get("opp_1h"), 0), _int_or(f.get("opp_2h"), 0),
              _int_or(f.get("our_pk")), _int_or(f.get("opp_pk")),
              _int_or(f.get("mvp_uid")), f.get("memo", "").strip()))
        flash("試合結果を保存しました。", "success")
        return redirect(url_for("event_detail", eid=eid))

    # Members who answered "attending" are listed first in the lineup editor.
    members = db.query("""
        select u.uid, u.uname, u.number, u.position, a.status, l.role
        from users u
        left join attendance a on a.uid = u.uid and a.eid = %s
        left join lineups l on l.uid = u.uid and l.eid = %s
        order by case when a.status = 'yes' then 0 else 1 end, coalesce(u.number, 999), u.uname
    """, (eid, eid))
    return render_template("result_form.html", title="試合結果の入力", ev=ev,
                           result=_match_result(eid), goals=_goals(eid), members=members)


@app.route("/events/<int:eid>/goals", methods=["POST"])
@admin_required
def goal_add(eid):
    f = request.form
    side = f.get("side") if f.get("side") in ("our", "opp") else "our"
    half = _int_or(f.get("half"), 1)
    if half not in HALVES:
        half = 1
    scorer_uid = _int_or(f.get("scorer_uid")) if side == "our" else None
    assist_uid = _int_or(f.get("assist_uid")) if side == "our" else None
    db.execute("""
        insert into goals (eid, side, scorer_uid, assist_uid, half, minute, note)
        values (%s, %s, %s, %s, %s, %s, %s)
    """, (eid, side, scorer_uid, assist_uid, half, _int_or(f.get("minute")), f.get("note", "").strip()))
    flash("得点を追加しました。", "success")
    return redirect(url_for("result_edit", eid=eid))


@app.route("/events/<int:eid>/goals/<int:gid>/delete", methods=["POST"])
@admin_required
def goal_delete(eid, gid):
    db.execute("delete from goals where gid = %s and eid = %s", (gid, eid))
    flash("得点を削除しました。", "success")
    return redirect(url_for("result_edit", eid=eid))


def _seasons(matches_only=False):
    where = " and etype = 'match'" if matches_only else ""
    return [r["season"] for r in db.query(
        f"select distinct season from events where season is not null and season <> '' {where} order by season desc")]


def _competitions(season):
    return [r["competition"] for r in db.query("""
        select distinct competition from events
        where etype = 'match' and season = %s and competition is not null and competition <> ''
        order by competition
    """, (season,))]


@app.route("/scores")
@login_required
def scores():
    seasons = _seasons(matches_only=True)
    season = request.args.get("season") or (seasons[0] if seasons else config.CURRENT_SEASON)
    competition = request.args.get("competition", "")
    matches, summary = _match_list(season=season, competition=competition)
    return render_template("scores.html", title="スコア", matches=matches, summary=summary,
                           seasons=seasons, season=season,
                           competitions=_competitions(season), competition=competition)


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

def _scope_filter(season, competition):
    """SQL fragment restricting ``events e`` to a season / competition (None = all-time)."""
    sql, params = "", []
    if season:
        sql += " and e.season = %s"
        params.append(season)
        if competition:
            sql += " and e.competition = %s"
            params.append(competition)
    return sql, params


def _ranked(rows):
    """Attach competition-style ranks (1, 2, 2, 4) to rows sorted by ``n`` desc."""
    out, prev, rank = [], None, 0
    for i, r in enumerate(rows, 1):
        if r["n"] != prev:
            rank, prev = i, r["n"]
        d = dict(r)
        d["rank"] = rank
        out.append(d)
    return out


def _ranking(sql, params):
    return _ranked(db.query(sql, tuple(params)))


@app.route("/stats")
@login_required
def stats():
    seasons = _seasons()
    if config.CURRENT_SEASON not in seasons:
        seasons.insert(0, config.CURRENT_SEASON)
    season = request.args.get("season") or seasons[0]
    if season == "all":
        season = None
    competition = request.args.get("competition", "") if season else ""
    competitions = _competitions(season) if season else []

    scope, params = _scope_filter(season, competition)
    today = date.today().isoformat()
    by_player = "group by u.uid, u.uname, u.number order by n desc, u.uname"

    goals = _ranking(f"""
        select u.uid, u.uname, u.number, count(*) as n
        from goals g join events e on e.eid = g.eid join users u on u.uid = g.scorer_uid
        where g.side = 'our' {scope} {by_player}""", params)
    assists = _ranking(f"""
        select u.uid, u.uname, u.number, count(*) as n
        from goals g join events e on e.eid = g.eid join users u on u.uid = g.assist_uid
        where g.side = 'our' {scope} {by_player}""", params)
    mvps = _ranking(f"""
        select u.uid, u.uname, u.number, count(*) as n
        from match_results r join events e on e.eid = r.eid join users u on u.uid = r.mvp_uid
        where 1 = 1 {scope} {by_player}""", params)
    apps = _ranking(f"""
        select u.uid, u.uname, u.number, count(*) as n
        from lineups l join events e on e.eid = l.eid join users u on u.uid = l.uid
        where 1 = 1 {scope} {by_player}""", params)

    # Attendance counts only past, non-cancelled events; ``held`` is the denominator.
    held = db.query(f"""
        select count(*) as c from events e
        where e.cancelled = 0 and e.event_date <= %s {scope}
    """, (today, *params), one=True)["c"]
    attendance = _ranking(f"""
        select u.uid, u.uname, u.number, count(*) as n
        from attendance a join events e on e.eid = a.eid join users u on u.uid = a.uid
        where a.status = 'yes' and e.cancelled = 0 and e.event_date <= %s {scope} {by_player}""",
        (today, *params))

    _, team = _match_list(season=season, competition=competition)

    uid = g.user["uid"]
    mine = {key: next((r["n"] for r in rows if r["uid"] == uid), 0)
            for key, rows in (("goals", goals), ("assists", assists), ("mvps", mvps),
                              ("attendance", attendance), ("apps", apps))}
    mine["rate"] = round(100 * mine["attendance"] / held) if held else None

    return render_template("stats.html", title="スタッツ",
                           seasons=seasons, season=season,
                           competitions=competitions, competition=competition,
                           goals=goals, assists=assists, mvps=mvps, attendance=attendance, apps=apps,
                           held=held, team=team, mine=mine)


# ---------------------------------------------------------------------------
# Posts and comments
# ---------------------------------------------------------------------------

POST_SQL = """
select p.*, u.uname as author,
  (select count(*) from comments c where c.pid = p.pid) as comment_count
from posts p
left join users u on u.uid = p.uid
"""


@app.route("/posts")
@login_required
def posts():
    rows = db.query(POST_SQL + " order by p.pinned desc, p.created_at desc")
    return render_template("posts.html", title="投稿", posts=rows)


@app.route("/posts/new", methods=["GET", "POST"])
@login_required
def post_new():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        body = request.form.get("body", "").strip()
        if not body:
            flash("本文を入力してください。", "danger")
            return render_template("post_form.html", title="投稿する", post={"title": title, "body": body})
        db.execute("insert into posts (uid, title, body, created_at) values (%s, %s, %s, %s)",
                   (g.user["uid"], title, body, now_str()))
        flash("投稿しました。", "success")
        return redirect(url_for("posts"))
    return render_template("post_form.html", title="投稿する", post=None)


@app.route("/posts/<int:pid>")
@login_required
def post_detail(pid):
    post = db.query(POST_SQL + " where p.pid = %s", (pid,), one=True)
    if post is None:
        abort(404)
    comments = db.query("""
        select c.*, u.uname as author
        from comments c
        left join users u on u.uid = c.uid
        where c.pid = %s
        order by c.created_at
    """, (pid,))
    return render_template("post_detail.html", title=post["title"] or "投稿", post=post, comments=comments)


@app.route("/posts/<int:pid>/comment", methods=["POST"])
@login_required
def comment_add(pid):
    if db.query("select pid from posts where pid = %s", (pid,), one=True) is None:
        abort(404)
    body = request.form.get("body", "").strip()
    if not body:
        flash("コメントを入力してください。", "danger")
    else:
        db.execute("insert into comments (pid, uid, body, created_at) values (%s, %s, %s, %s)",
                   (pid, g.user["uid"], body, now_str()))
        flash("コメントしました。", "success")
    return redirect(url_for("post_detail", pid=pid))


@app.route("/comments/<int:cid>/delete", methods=["POST"])
@login_required
def comment_delete(cid):
    c = db.query("select * from comments where cid = %s", (cid,), one=True)
    if c is None:
        abort(404)
    if not _can_delete(c["uid"]):
        flash("自分のコメントだけ削除できます。", "warning")
    else:
        db.execute("delete from comments where cid = %s", (cid,))
        flash("コメントを削除しました。", "success")
    return redirect(url_for("post_detail", pid=c["pid"]))


@app.route("/posts/<int:pid>/delete", methods=["POST"])
@login_required
def post_delete(pid):
    post = db.query("select * from posts where pid = %s", (pid,), one=True)
    if post is None:
        abort(404)
    if not _can_delete(post["uid"]):
        flash("自分の投稿だけ削除できます。", "warning")
        return redirect(url_for("post_detail", pid=pid))
    db.execute("delete from comments where pid = %s", (pid,))
    db.execute("delete from posts where pid = %s", (pid,))
    flash("投稿を削除しました。", "success")
    return redirect(url_for("posts"))


@app.route("/posts/<int:pid>/pin", methods=["POST"])
@admin_required
def post_pin(pid):
    post = db.query("select pinned from posts where pid = %s", (pid,), one=True)
    if post is None:
        abort(404)
    db.execute("update posts set pinned = %s where pid = %s", (0 if post["pinned"] else 1, pid))
    flash("固定を解除しました。" if post["pinned"] else "投稿を上部に固定しました。", "success")
    return redirect(url_for("post_detail", pid=pid))


# ---------------------------------------------------------------------------
# Lineups
# ---------------------------------------------------------------------------

def _lineup(eid):
    rows = db.query("""
        select l.role, u.uid, u.uname, u.number, u.position, u.captain
        from lineups l
        join users u on u.uid = l.uid
        where l.eid = %s
        order by case l.role when 'starter' then 0 else 1 end, coalesce(u.number, 999), u.uname
    """, (eid,))
    return {"starter": [r for r in rows if r["role"] == "starter"],
            "sub": [r for r in rows if r["role"] == "sub"]}


@app.route("/events/<int:eid>/lineup", methods=["POST"])
@admin_required
def lineup_save(eid):
    """Replace the lineup from ``role_<uid>`` form fields (starter / sub / empty)."""
    if db.query("select eid from events where eid = %s and etype = 'match'", (eid,), one=True) is None:
        abort(404)
    db.execute("delete from lineups where eid = %s", (eid,))
    count = 0
    for key, value in request.form.items():
        if key.startswith("role_") and value in LINEUP_ROLES:
            uid = _int_or(key[5:])
            if uid:
                db.execute("insert into lineups (eid, uid, role) values (%s, %s, %s)", (eid, uid, value))
                count += 1
    flash(f"出場メンバーを保存しました（{count}人）。", "success")
    return redirect(url_for("result_edit", eid=eid) + "#lineup")


# ---------------------------------------------------------------------------
# Photos and album
# ---------------------------------------------------------------------------

def _photos(eid):
    return db.query("""
        select p.*, u.uname as uploader
        from photos p
        left join users u on u.uid = p.uid
        where p.eid = %s
        order by p.created_at desc, p.phid desc
    """, (eid,))


def _shrink_image(path, max_px=1600):
    """Downscale large uploads and fix EXIF orientation. No-op without Pillow."""
    try:
        from PIL import Image, ImageOps
    except ImportError:
        return
    try:
        with Image.open(path) as im:
            im = ImageOps.exif_transpose(im)
            if max(im.size) > max_px:
                im.thumbnail((max_px, max_px))
            im.save(path)
    except Exception:
        pass


@app.route("/events/<int:eid>/photos", methods=["POST"])
@login_required
def photo_upload(eid):
    if db.query("select eid from events where eid = %s", (eid,), one=True) is None:
        abort(404)
    files = [f for f in request.files.getlist("photos") if f and f.filename]
    if not files:
        flash("写真を選んでください。", "danger")
        return redirect(url_for("event_detail", eid=eid))

    folder = os.path.join(UPLOAD_DIR, str(eid))
    try:
        os.makedirs(folder, exist_ok=True)
    except OSError:
        flash("サーバに保存用フォルダを作れませんでした。", "danger")
        return redirect(url_for("event_detail", eid=eid))

    saved = 0
    caption = request.form.get("caption", "").strip()
    for f in files:
        ext = secure_filename(f.filename).rsplit(".", 1)[-1].lower() if "." in f.filename else ""
        if ext not in PHOTO_EXTS:
            continue
        name = f"{secrets.token_hex(8)}.{ext}"  # unguessable, never the original name
        path = os.path.join(folder, name)
        f.save(path)
        _shrink_image(path)
        db.execute("insert into photos (eid, uid, filename, caption, created_at) values (%s, %s, %s, %s, %s)",
                   (eid, g.user["uid"], name, caption, now_str()))
        saved += 1

    flash(f"{saved}枚の写真を追加しました。" if saved else "対応していない形式です（jpg / png / gif / webp）。",
          "success" if saved else "danger")
    return redirect(url_for("event_detail", eid=eid) + "#photos")


@app.route("/photos/<int:phid>/delete", methods=["POST"])
@login_required
def photo_delete(phid):
    ph = db.query("select * from photos where phid = %s", (phid,), one=True)
    if ph is None:
        abort(404)
    if not _can_delete(ph["uid"]):
        flash("自分が追加した写真だけ削除できます。", "warning")
        return redirect(url_for("event_detail", eid=ph["eid"]))
    db.execute("delete from photos where phid = %s", (phid,))
    try:
        os.remove(os.path.join(UPLOAD_DIR, str(ph["eid"]), ph["filename"]))
    except OSError:
        pass
    flash("写真を削除しました。", "success")
    return redirect(url_for("event_detail", eid=ph["eid"]) + "#photos")


@app.route("/album")
@login_required
def album():
    rows = db.query("""
        select p.phid, p.eid, p.filename, p.caption, e.title, e.event_date, e.opponent
        from photos p
        join events e on e.eid = p.eid
        order by e.event_date desc, p.created_at desc
    """)
    groups = []  # [(event row, [photo rows]), ...] newest event first
    for r in rows:
        if not groups or groups[-1][0]["eid"] != r["eid"]:
            groups.append((r, []))
        groups[-1][1].append(r)
    return render_template("album.html", title="アルバム", groups=groups, total=len(rows))


# ---------------------------------------------------------------------------
# Members and profiles
# ---------------------------------------------------------------------------

@app.route("/members")
@login_required
def members():
    rows = db.query("""
        select uid, uname, number, position, role, captain
        from users
        order by coalesce(number, 999), uname
    """)
    groups = {p: [] for p in POSITIONS}
    groups[None] = []
    for r in rows:
        groups[r["position"] if r["position"] in POSITIONS else None].append(r)
    return render_template("members.html", title="メンバー", groups=groups, total=len(rows))


def _player_stats(uid, season):
    """Per-player totals for one season, or all-time when ``season`` is None."""
    scope, params = _scope_filter(season, None)
    today = date.today().isoformat()

    def count(sql, extra):
        return db.query(sql, tuple(extra) + tuple(params), one=True)["c"]

    goals = count(f"""select count(*) as c from goals g join events e on e.eid = g.eid
                      where g.side = 'our' and g.scorer_uid = %s {scope}""", (uid,))
    assists = count(f"""select count(*) as c from goals g join events e on e.eid = g.eid
                        where g.side = 'our' and g.assist_uid = %s {scope}""", (uid,))
    mvps = count(f"""select count(*) as c from match_results r join events e on e.eid = r.eid
                     where r.mvp_uid = %s {scope}""", (uid,))
    held = count(f"""select count(*) as c from events e
                     where e.cancelled = 0 and e.event_date <= %s {scope}""", (today,))
    attended = count(f"""select count(*) as c from attendance a join events e on e.eid = a.eid
                         where a.uid = %s and a.status = 'yes' and e.cancelled = 0 and e.event_date <= %s {scope}""",
                     (uid, today))
    matches_held = count(f"""select count(*) as c from events e
                             where e.etype = 'match' and e.cancelled = 0 and e.event_date <= %s {scope}""", (today,))
    matches_attended = count(f"""select count(*) as c from attendance a join events e on e.eid = a.eid
                                 where a.uid = %s and a.status = 'yes' and e.etype = 'match'
                                   and e.cancelled = 0 and e.event_date <= %s {scope}""", (uid, today))
    apps = count(f"""select count(*) as c from lineups l join events e on e.eid = l.eid
                     where l.uid = %s {scope}""", (uid,))
    starts = count(f"""select count(*) as c from lineups l join events e on e.eid = l.eid
                       where l.uid = %s and l.role = 'starter' {scope}""", (uid,))
    return {
        "goals": goals, "assists": assists, "mvps": mvps, "apps": apps, "starts": starts,
        "attended": attended, "held": held,
        "rate": round(100 * attended / held) if held else None,
        "matches_attended": matches_attended, "matches_held": matches_held,
    }


@app.route("/members/<int:uid>")
@login_required
def member_detail(uid):
    u = db.query("select * from users where uid = %s", (uid,), one=True)
    if u is None:
        abort(404)

    stats = {"season": _player_stats(uid, config.CURRENT_SEASON), "total": _player_stats(uid, None)}
    scoring = db.query("""
        select e.eid, e.title, e.event_date, e.opponent, e.competition, e.season, count(*) as n
        from goals g
        join events e on e.eid = g.eid
        where g.side = 'our' and g.scorer_uid = %s
        group by e.eid, e.title, e.event_date, e.opponent, e.competition, e.season
        order by e.event_date desc
        limit 10
    """, (uid,))
    mvp_matches = db.query("""
        select e.eid, e.title, e.event_date, e.opponent, e.season
        from match_results r
        join events e on e.eid = r.eid
        where r.mvp_uid = %s
        order by e.event_date desc
        limit 10
    """, (uid,))
    return render_template("member_detail.html", title=u["uname"], u=u, age=_age(u["birthdate"]),
                           stats=stats, scoring=scoring, mvp_matches=mvp_matches,
                           season=config.CURRENT_SEASON)


def _save_profile(uid, allow_role=False, is_admin=False):
    """Persist the profile form. Returns an error message, or None on success."""
    f = request.form
    uname = f.get("uname", "").strip()
    if not uname:
        return "名前は必須です。"
    position = f.get("position") if f.get("position") in POSITIONS else None
    foot = f.get("foot") if f.get("foot") in FEET else None
    birthdate = f.get("birthdate", "").strip() or None
    if birthdate:
        try:
            date.fromisoformat(birthdate)
        except ValueError:
            return "生年月日の形式が正しくありません。"

    db.execute("""
        update users
           set uname = %s, number = %s, position = %s,
               height_cm = %s, weight_kg = %s, birthdate = %s, foot = %s, intro = %s
         where uid = %s
    """, (uname, _int_or(f.get("number")), position,
          _int_or(f.get("height_cm")), _int_or(f.get("weight_kg")), birthdate, foot,
          f.get("intro", "").strip(), uid))

    if allow_role and f.get("role") in ("admin", "member"):
        db.execute("update users set role = %s where uid = %s", (f.get("role"), uid))
    if is_admin:
        db.execute("update users set captain = %s where uid = %s", (1 if f.get("captain") == "on" else 0, uid))
    return None


@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    if request.method == "POST":
        err = _save_profile(g.user["uid"])
        flash(err or "プロフィールを更新しました。", "danger" if err else "success")
        return redirect(url_for("profile"))
    return render_template("profile.html", title="プロフィール", u=g.user,
                           form_action=url_for("profile"), is_admin_edit=False)


@app.route("/members/<int:uid>/edit", methods=["GET", "POST"])
@admin_required
def member_edit(uid):
    u = db.query("select * from users where uid = %s", (uid,), one=True)
    if u is None:
        abort(404)
    if request.method == "POST":
        # Admins cannot demote themselves, so there is always at least one admin.
        err = _save_profile(uid, allow_role=(uid != g.user["uid"]), is_admin=True)
        flash(err or f"{request.form.get('uname', '').strip()} さんのプロフィールを更新しました。",
              "danger" if err else "success")
        return redirect(url_for("member_edit", uid=uid) if err else url_for("member_detail", uid=uid))
    return render_template("profile.html", title=f"{u['uname']} さんの編集", u=u,
                           form_action=url_for("member_edit", uid=uid), is_admin_edit=True)


# ---------------------------------------------------------------------------
# Error pages, web manifest
# ---------------------------------------------------------------------------

@app.errorhandler(404)
def not_found(e):
    return render_template("error.html", title="ページが見つかりません", code=404,
                           message="お探しのページは見つかりませんでした。削除されたか、URLが間違っている可能性があります。"), 404


@app.errorhandler(500)
def server_error(e):
    return render_template("error.html", title="エラー", code=500,
                           message="サーバでエラーが発生しました。時間をおいてもう一度お試しください。"), 500


@app.route("/manifest.webmanifest")
def manifest():
    """PWA manifest. Paths are built with url_for so sub-path deployments work."""
    data = {
        "name": config.TEAM_NAME,
        "short_name": config.TEAM_NAME,
        "start_url": url_for("index"),
        "scope": url_for("index"),
        "display": "standalone",
        "background_color": "#ffffff",
        "theme_color": config.TEAM_COLOR,
        "icons": [
            {"src": url_for("static", filename="icons/icon-192.png"), "sizes": "192x192", "type": "image/png"},
            {"src": url_for("static", filename="icons/icon-512.png"), "sizes": "512x512", "type": "image/png"},
        ],
    }
    resp = jsonify(data)
    resp.mimetype = "application/manifest+json"
    return resp


if __name__ == "__main__":
    app.run(debug=True, port=config.DEV_PORT)
