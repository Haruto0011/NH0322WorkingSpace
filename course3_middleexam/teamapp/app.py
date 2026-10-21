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
    events = db.query(
        EVENT_LIST_SQL + " where e.event_date >= %s order by e.event_date, e.start_time limit 5",
        (g.user["uid"], today))
    return render_template("index.html", title="ホーム", events=events)


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

    return render_template("event_detail.html", title=ev["title"],
                           ev=ev, groups=groups, counts=counts, mine=mine)


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
    }


@app.route("/events/new", methods=["GET", "POST"])
@admin_required
def event_new():
    if request.method == "POST":
        f = _event_from_form()
        if not f["title"] or not f["event_date"]:
            flash("タイトルと日付は必須です。", "danger")
            return render_template("event_form.html", title="予定を追加", ev=f)
        db.execute("""
            insert into events (etype, title, event_date, start_time, end_time,
                                place, opponent, note, created_by)
            values (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (f["etype"], f["title"], f["event_date"], f["start_time"], f["end_time"],
              f["place"], f["opponent"], f["note"], g.user["uid"]))
        flash("予定を追加しました。", "success")
        return redirect(url_for("events"))
    return render_template("event_form.html", title="予定を追加", ev=None)


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
            return render_template("event_form.html", title="予定を編集", ev=f)
        db.execute("""
            update events
               set etype = %s, title = %s, event_date = %s, start_time = %s, end_time = %s,
                   place = %s, opponent = %s, note = %s
             where eid = %s
        """, (f["etype"], f["title"], f["event_date"], f["start_time"], f["end_time"],
              f["place"], f["opponent"], f["note"], eid))
        flash("予定を更新しました。", "success")
        return redirect(url_for("event_detail", eid=eid))
    return render_template("event_form.html", title="予定を編集", ev=ev)


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
    db.execute("delete from attendance where eid = %s", (eid,))  # 先に出欠を消す（外部キー）
    db.execute("delete from events where eid = %s", (eid,))
    flash("予定を削除しました。", "success")
    return redirect(url_for("events"))


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
