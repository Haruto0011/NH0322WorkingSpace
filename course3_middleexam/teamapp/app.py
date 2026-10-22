"""
サッカーチーム管理サイト（Phase 1 モック版）

画面の流れ
  /login → /（ホーム：直近の予定と自分の回答状況）
          → /events（予定一覧） → /events/<id>（詳細・出欠回答）
          → /members（メンバー一覧） → /profile（自分のプロフィール）
  管理者だけ: /events/new（追加） /events/<id>/edit（編集） /events/<id>/delete（削除）

DBアクセスは db.py にまとめてある（SQL は PostgreSQL / SQLite 両方で動く書き方）。
リンクはすべて url_for() で作る。サーバでは /s0000001/ のような
サブパスにデプロイされるので、"/events" と直書きすると壊れるため。
"""
import math
from datetime import date, timedelta
from functools import wraps

from flask import (Flask, abort, flash, g, redirect, render_template, request,
                   session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

import config
import db

app = Flask(__name__)
app.config["SECRET_KEY"] = config.SECRET_KEY
app.permanent_session_lifetime = timedelta(days=30)  # ログイン状態を30日保持
db.init_app(app)

# 画面で使う選択肢。ここを変えれば全画面に反映される
ETYPES = {"practice": "練習", "match": "試合", "other": "その他"}
POSITIONS = ["GK", "DF", "MF", "FW"]
STATUSES = {"yes": "出席", "no": "欠席"}   # 回答していない人は「未回答」扱い
HALVES = {1: "前半", 2: "後半"}
OUTCOMES = {"win": "勝ち", "draw": "引き分け", "loss": "負け"}
WEEKDAYS = "月火水木金土日"


# =========================================================
# 共通処理
# =========================================================

@app.before_request
def before_request():
    # 本番サーバでは https に強制（config.FORCE_HTTPS = True にする）
    if config.FORCE_HTTPS and not request.is_secure:
        return redirect(request.url.replace("http://", "https://", 1))

    # ログイン中なら g.user にユーザ情報を入れておく。テンプレートからも g.user で参照できる
    g.user = None
    if session.get("uid"):
        g.user = db.query("select * from users where uid = %s", (session["uid"],), one=True)


@app.context_processor
def inject_globals():
    # すべてのテンプレートで使える変数
    return {
        "team_name": config.TEAM_NAME,
        "ETYPES": ETYPES,
        "POSITIONS": POSITIONS,
        "STATUSES": STATUSES,
        "HALVES": HALVES,
        "OUTCOMES": OUTCOMES,
    }


def login_required(f):
    """ルート関数の上に @login_required と書くと、未ログインなら /login へ飛ばす"""
    @wraps(f)
    def wrapper(*args, **kwargs):
        if g.user is None:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper


def admin_required(f):
    """管理者（role = 'admin'）以外は弾く"""
    @wraps(f)
    def wrapper(*args, **kwargs):
        if g.user is None:
            return redirect(url_for("login"))
        if g.user["role"] != "admin":
            flash("この操作は管理者のみ行えます。", "warning")
            return redirect(url_for("index"))
        return f(*args, **kwargs)
    return wrapper


@app.template_filter("jdate")
def jdate(v):
    """テンプレート用: 2026-10-25 → 10/25(土)"""
    if not v:
        return ""
    if isinstance(v, str):          # SQLite は文字列、PostgreSQL は date 型で返ってくる
        v = date.fromisoformat(v)
    return f"{v.month}/{v.day}({WEEKDAYS[v.weekday()]})"


@app.template_filter("jtime")
def jtime(v):
    """テンプレート用: 19:00:00 → 19:00"""
    return str(v)[:5] if v else ""


# =========================================================
# 認証（講義資料 flskauth と同じルート名）
# =========================================================

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

    # 最初に登録した人を自動で管理者にする
    count = db.query("select count(*) as c from users", one=True)["c"]
    role = "admin" if count == 0 else "member"

    # パスワードは平文で保存しない（werkzeug のハッシュ関数を使う）
    pw_hash = generate_password_hash(pwf1, method="pbkdf2:sha256")
    db.execute("insert into users (uname, email, pw, role) values (%s, %s, %s, %s)",
               (unf, emf, pw_hash, role))

    flash("登録しました。ログインしてください。", "success")
    return redirect(url_for("login"))


@app.route("/login")
def login():
    if g.user:
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
    return redirect(url_for("login"))


# =========================================================
# ホーム・予定
# =========================================================

# 予定一覧に「参加人数」と「自分の回答」を付けて取る共通SQL。パラメータの1つ目は自分の uid
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

    # 直近の予定（5件）
    events = db.query(
        EVENT_LIST_SQL + " where e.event_date >= %s order by e.event_date, e.start_time limit 5",
        (uid, today))

    # 自分がまだ出欠を答えていない今後の予定の数（中止は除く）
    pending = db.query("""
        select count(*) as c from events e
        where e.event_date >= %s and e.cancelled = 0
          and not exists (select 1 from attendance a where a.eid = e.eid and a.uid = %s)
    """, (today, uid), one=True)["c"]

    # 最新の試合結果（1件）と、今シーズンの成績
    latest_list, _ = _match_list(limit=1)
    latest = latest_list[0] if latest_list else None
    _, summary = _match_list(season=config.CURRENT_SEASON)

    member_count = db.query("select count(*) as c from users", one=True)["c"]

    return render_template("index.html", title="ホーム", events=events, pending=pending,
                           latest=latest, summary=summary, donut=_donut(summary),
                           season=config.CURRENT_SEASON, member_count=member_count)


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


@app.route("/events/<int:eid>")
@login_required
def event_detail(eid):
    # 予定 ＋ 作成者の名前
    ev = db.query("""
        select e.*, u.uname as creator
        from events e
        left join users u on u.uid = e.created_by
        where e.eid = %s
    """, (eid,), one=True)
    if ev is None:
        abort(404)

    # 全メンバー ＋ この予定への回答（未回答の人は status が None になる）
    members = db.query("""
        select u.uid, u.uname, u.number, u.position, a.status, a.comment
        from users u
        left join attendance a on a.uid = u.uid and a.eid = %s
        order by coalesce(u.number, 999), u.uname
    """, (eid,))

    # 出席 / 欠席 / 未回答 の3グループに分ける
    groups = {"yes": [], "no": [], "none": []}
    mine = None
    for m in members:
        key = m["status"] if m["status"] in STATUSES else "none"
        groups[key].append(m)
        if m["uid"] == g.user["uid"]:
            mine = m
    counts = {key: len(lst) for key, lst in groups.items()}

    # 試合なら結果と得点も
    result = goals = score = None
    if ev["etype"] == "match":
        result = _match_result(eid)
        goals = _goals(eid)
        if result:
            our = result["our_1h"] + result["our_2h"]
            opp = result["opp_1h"] + result["opp_2h"]
            score = {"our": our, "opp": opp, "outcome": _outcome(our, opp)}

    return render_template("event_detail.html", title=ev["title"],
                           ev=ev, groups=groups, counts=counts, mine=mine,
                           result=result, goals=goals, score=score)


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

    # 未回答なら insert、回答済みなら update（UPSERT）
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


# ---------- 予定の追加・編集・削除（管理者のみ） ----------

def _event_from_form():
    """フォームの内容を辞書にまとめる（追加と編集で共通）"""
    etype = request.form.get("etype")
    return {
        "etype": etype if etype in ETYPES else "practice",
        "title": request.form.get("title", "").strip(),
        "event_date": request.form.get("event_date", ""),
        "start_time": request.form.get("start_time") or None,   # 空欄なら NULL
        "end_time": request.form.get("end_time") or None,
        "place": request.form.get("place", "").strip(),
        "opponent": request.form.get("opponent", "").strip(),
        "note": request.form.get("note", "").strip(),
        "season": request.form.get("season", "").strip() or config.CURRENT_SEASON,
        "competition": request.form.get("competition", "").strip(),
    }


def _form_choices():
    """予定フォームの入力候補（これまでに使ったシーズン名・大会名）"""
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
        db.execute("""
            insert into events (etype, title, event_date, start_time, end_time,
                                place, opponent, note, season, competition, created_by)
            values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (f["etype"], f["title"], f["event_date"], f["start_time"], f["end_time"],
              f["place"], f["opponent"], f["note"], f["season"], f["competition"], g.user["uid"]))
        flash("予定を追加しました。", "success")
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
    """中止 ⇔ 中止取り消し を切り替える（予定自体は消さない）"""
    ev = db.query("select cancelled from events where eid = %s", (eid,), one=True)
    if ev is None:
        abort(404)
    new_value = 0 if ev["cancelled"] else 1
    db.execute("update events set cancelled = %s where eid = %s", (new_value, eid))
    flash("予定を中止にしました。" if new_value else "中止を取り消しました。", "success")
    return redirect(url_for("event_detail", eid=eid))


@app.route("/events/<int:eid>/delete", methods=["POST"])
@admin_required
def event_delete(eid):
    # 先に紐づくデータを消す（外部キー）
    db.execute("delete from attendance where eid = %s", (eid,))
    db.execute("delete from goals where eid = %s", (eid,))
    db.execute("delete from match_results where eid = %s", (eid,))
    db.execute("delete from events where eid = %s", (eid,))
    flash("予定を削除しました。", "success")
    return redirect(url_for("events"))


# =========================================================
# 試合結果・得点・スコア一覧
# =========================================================

def _match_result(eid):
    """試合結果（なければ None）。MVP の名前も付けて返す"""
    return db.query("""
        select r.*, u.uname as mvp
        from match_results r
        left join users u on u.uid = r.mvp_uid
        where r.eid = %s
    """, (eid,), one=True)


def _goals(eid):
    """得点の一覧（前半→後半、時間順）。得点者・アシストの名前付き"""
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


def _int_or(value, default=None):
    """フォームの数値欄を int にする（空欄なら default）"""
    value = (value or "").strip()
    return int(value) if value.isdigit() else default


def _match_list(season=None, competition=None, limit=None):
    """結果が入力済みの試合の一覧（新しい順）と、勝敗・得失点のまとめ。
    ホーム（最新1件・今シーズン成績）とスコア一覧の両方で使う"""
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

    matches = [dict(r) for r in db.query(sql, tuple(params))]   # dict にして計算結果を足す
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


DONUT_R = 40                       # ドーナツグラフの半径（SVGの座標）
DONUT_C = 2 * math.pi * DONUT_R    # 円周


def _donut(summary):
    """勝ち/引き分け/負け をドーナツグラフにするための円弧の長さを計算する。
    SVG の stroke-dasharray（線の長さ, 空白の長さ）と stroke-dashoffset（開始位置）に渡す"""
    total = summary["games"]
    segments = []
    offset = 0.0
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
    """試合結果の入力・編集（スコア・MVP・メモ）。得点の追加は goal_add"""
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

    members = db.query("select uid, uname, number from users order by coalesce(number, 999), uname")
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
    # 相手の得点には得点者・アシストを付けない
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


@app.route("/scores")
@login_required
def scores():
    """試合結果の一覧。シーズン（タブ）と大会（絞り込み）で切り替える"""
    seasons = [r["season"] for r in db.query("""
        select distinct season from events
        where etype = 'match' and season is not null and season <> ''
        order by season desc
    """)]
    season = request.args.get("season") or (seasons[0] if seasons else config.CURRENT_SEASON)
    competitions = [r["competition"] for r in db.query("""
        select distinct competition from events
        where etype = 'match' and season = %s and competition is not null and competition <> ''
        order by competition
    """, (season,))]
    competition = request.args.get("competition", "")

    matches, summary = _match_list(season=season, competition=competition)

    return render_template("scores.html", title="スコア", matches=matches, summary=summary,
                           seasons=seasons, season=season,
                           competitions=competitions, competition=competition)


# =========================================================
# メンバー・プロフィール
# =========================================================

@app.route("/members")
@login_required
def members():
    rows = db.query("""
        select uid, uname, number, position, role
        from users
        order by coalesce(number, 999), uname
    """)
    return render_template("members.html", title="メンバー", members=rows)


@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    if request.method == "POST":
        uname = request.form.get("uname", "").strip()
        number = request.form.get("number", "").strip()
        position = request.form.get("position") or None

        if not uname:
            flash("名前は必須です。", "danger")
            return redirect(url_for("profile"))
        number = int(number) if number.isdigit() else None
        if position not in POSITIONS:
            position = None

        db.execute("update users set uname = %s, number = %s, position = %s where uid = %s",
                   (uname, number, position, g.user["uid"]))
        flash("プロフィールを更新しました。", "success")
        return redirect(url_for("profile"))
    return render_template("profile.html", title="プロフィール")


# 手元で動かすとき:  python app.py  → http://127.0.0.1:5000
if __name__ == "__main__":
    app.run(debug=True)
