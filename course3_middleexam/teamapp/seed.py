"""
Populate an empty database with demo data.

    python seed.py

Creates 20 sample members plus the owner account from config.py, two seasons
of events with attendance, match results, goals, lineups, posts and sample
photos. Generation is seeded, so repeated runs produce identical data.
All sample accounts use the password ``pass1234`` (e.g. admin@example.com).
"""
import os
import random
from datetime import date, datetime, timedelta

from werkzeug.security import generate_password_hash

import config
import db

rng = random.Random(2026)
conn = db.get_conn()
cur = conn.cursor()
q = db.convert

cur.execute(q("select count(*) as c from users"))
if cur.fetchone()["c"] > 0:
    print("database already has users; nothing to do")
    conn.close()
    raise SystemExit

pw = generate_password_hash("pass1234", method="pbkdf2:sha256")
today = date.today()
season = config.CURRENT_SEASON
prev_season = str(int(season) - 1)


def ts(days_ago, hour=20):
    return (datetime.combine(today, datetime.min.time()) - timedelta(days=days_ago)).replace(hour=hour) \
        .strftime("%Y-%m-%d %H:%M:%S")


# --- Members ---------------------------------------------------------------
members = [
    # name, email key, role, number, position, height, weight, birthdate, foot, intro
    ("監督",   "admin",     "admin",  None, None, None, None, None,         None, "今年こそ昇格！"),
    ("田中",   "tanaka",    "member", 1,  "GK", 183, 78, "2003-04-12", "右", "キャプテン。ビッグセーブで流れを引き寄せます"),
    ("山本",   "yamamoto",  "member", 21, "GK", 178, 74, "2005-11-03", "右", ""),
    ("鈴木",   "suzuki",    "member", 2,  "DF", 175, 70, "2004-01-25", "右", ""),
    ("渡辺",   "watanabe",  "member", 3,  "DF", 180, 75, "2003-09-08", "左", "左SB。クロスが武器"),
    ("中村",   "nakamura",  "member", 4,  "DF", 182, 77, "2002-06-30", "右", ""),
    ("小林",   "kobayashi", "member", 5,  "DF", 179, 76, "2004-12-14", "右", ""),
    ("加藤",   "kato",      "member", 13, "DF", 173, 68, "2005-03-19", "右", ""),
    ("吉田",   "yoshida",   "member", 15, "DF", 176, 71, "2005-08-02", "両", ""),
    ("山田",   "yamada",    "member", 6,  "MF", 172, 66, "2003-02-11", "右", "ボランチ"),
    ("松本",   "matsumoto", "member", 7,  "MF", 170, 64, "2004-07-23", "左", "ドリブルで仕掛けます"),
    ("佐藤",   "sato",      "member", 8,  "MF", 174, 68, "2003-10-05", "右", "セットプレーのキッカー"),
    ("高橋",   "takahashi", "member", 10, "MF", 171, 65, "2002-12-01", "右", "ゲームメイク担当"),
    ("井上",   "inoue",     "member", 14, "MF", 168, 62, "2005-05-27", "右", ""),
    ("木村",   "kimura",    "member", 16, "MF", 175, 69, "2004-04-09", "左", ""),
    ("林",     "hayashi",   "member", 17, "MF", 169, 63, "2005-09-15", "右", ""),
    ("伊藤",   "ito",       "member", 9,  "FW", 177, 72, "2003-07-18", "右", "得点王を狙います"),
    ("斎藤",   "saito",     "member", 11, "FW", 181, 76, "2004-03-03", "左", "ポストプレーが得意"),
    ("清水",   "shimizu",   "member", 18, "FW", 173, 67, "2005-01-20", "右", ""),
    ("森",     "mori",      "member", 19, "FW", 176, 70, "2005-10-10", "両", ""),
]
vice_captains = {"nakamura", "takahashi"}
for name, key, role, number, pos, h, w, bd, foot, intro in members:
    cur.execute(q("insert into users (uname, email, pw, role, number, position, height_cm, weight_kg, birthdate, foot, intro, captain, vice_captain) "
                  "values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"),
                (name, f"{key}@example.com", pw, role, number, pos, h, w, bd, foot, intro,
                 1 if key == "tanaka" else 0, 1 if key in vice_captains else 0))

cur.execute(q("select uid, position from users order by uid"))
rows = cur.fetchall()
uids = [r["uid"] for r in rows]
pos_of = {r["uid"]: r["position"] for r in rows}
admin_uid = uids[0]
players = uids[1:]

# Owner account (admin). Excluded from generated attendance and stats.
cur.execute(q("insert into users (uname, email, pw, role) values (%s, %s, %s, 'admin')"),
            (config.OWNER_NAME, config.OWNER_EMAIL.lower(),
             generate_password_hash(config.OWNER_PASSWORD, method="pbkdf2:sha256")))

# Alumni (status 'ob'). Not included in attendance or stats.
alumni = [
    # name, email key, number, position, height, weight, birthdate, foot, intro
    ("大野", "ono",      5,  "DF", 178, 74, "1999-05-21", "右", "2024年卒。初代キャプテン"),
    ("岡田", "okada",    10, "MF", 172, 66, "1999-11-02", "左", "2024年卒。現在は社会人リーグでプレー中"),
    ("藤田", "fujita",   9,  "FW", 180, 75, "2000-02-14", "右", "2025年卒。通算得点王"),
    ("村上", "murakami", 1,  "GK", 185, 80, "2000-08-30", "右", "2025年卒"),
    ("石井", "ishii",    7,  "MF", 169, 63, "2000-12-09", "右", "2025年卒。OB会幹事"),
    ("長谷川", "hasegawa", 3, "DF", 176, 72, "2001-03-17", "左", "2026年卒"),
]
for name, key, number, pos, h, w, bd, foot, intro in alumni:
    cur.execute(q("insert into users (uname, email, pw, role, number, position, height_cm, weight_kg, birthdate, foot, intro, status) "
                  "values (%s, %s, %s, 'member', %s, %s, %s, %s, %s, %s, %s, 'ob')"),
                (name, f"{key}@example.com", pw, number, pos, h, w, bd, foot, intro))

# Likelihood of scoring / assisting by position.
goal_weight = {"GK": 0, "DF": 1, "MF": 3, "FW": 6}
assist_weight = {"GK": 0, "DF": 2, "MF": 5, "FW": 3}


def pick(weights, exclude=None):
    cands = [u for u in players if weights[pos_of[u]] > 0 and u != exclude]
    return rng.choices(cands, weights=[weights[pos_of[u]] for u in cands])[0]


# --- Events ----------------------------------------------------------------
opponents = ["東京蹴球団", "FC PHOENIX", "杉並FC", "練馬ユナイテッド", "渋谷SC", "品川FC",
             "三鷹クラブ", "調布FC", "世田谷FC", "大田ユナイテッド", "北区FC", "足立SC"]
grounds = ["代々木公園サッカー場", "みらい平グラウンド", "駒沢第二球技場", "夢の島競技場", "多摩川緑地G"]


def add_event(etype, title, d, start, end, place, opp, note, season_, comp):
    cur.execute(q("insert into events (etype, title, event_date, start_time, end_time, place, opponent, note, "
                  "season, competition, created_by) values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"),
                (etype, title, d.isoformat(), start, end, place, opp, note, season_, comp, admin_uid))
    cur.execute(q("select max(eid) as m from events"))
    eid = cur.fetchone()["m"]
    events.append((eid, etype, d))
    return eid


events = []  # (eid, etype, date)

# Previous season: six matches with results.
for i in range(6):
    opp = opponents[i]
    comp = "東京都リーグ" if i < 4 else "東京カップ"
    title = f"リーグ戦 vs {opp}" if comp == "東京都リーグ" else f"東京カップ vs {opp}"
    add_event("match", title, today - timedelta(days=560 - i * 40), "14:00", "16:00",
              rng.choice(grounds), opp, "", prev_season, comp)

# Current season: weekly practice on Saturdays, 28 weeks back to 4 weeks ahead.
last_sat = today - timedelta(days=(today.weekday() - 5) % 7)
for w in range(-28, 5):
    note = rng.choice(["", "", "", "ビブス持参", "雨天時は中止連絡します", "終了後ミーティングあり"])
    add_event("practice", "通常練習", last_sat + timedelta(weeks=w), "19:00", "21:00", "〇〇グラウンド", "", note, season, "")

# Current season: 13 matches (10 played, 3 upcoming).
match_plan = [
    (-180, "練習試合", "三鷹クラブ"), (-160, "東京都リーグ", "東京蹴球団"), (-140, "東京都リーグ", "FC PHOENIX"),
    (-120, "東京都リーグ", "杉並FC"), (-100, "東京カップ", "練馬ユナイテッド"), (-80, "東京都リーグ", "渋谷SC"),
    (-60, "練習試合", "品川FC"), (-40, "東京カップ", "調布FC"), (-19, "東京都リーグ", "世田谷FC"),
    (-12, "東京都リーグ", "大田ユナイテッド"), (4, "練習試合", "北区FC"), (11, "東京カップ", "足立SC"),
    (25, "東京都リーグ", "三鷹クラブ"),
]
for offset, comp, opp in match_plan:
    title = {"東京都リーグ": f"リーグ戦 vs {opp}", "東京カップ": f"東京カップ vs {opp}"}.get(comp, f"練習試合 vs {opp}")
    note = rng.choice(["", "集合は開始45分前", "白ユニフォーム", "車出せる人は監督まで"])
    add_event("match", title, today + timedelta(days=offset), "13:50", "15:40", rng.choice(grounds), opp, note, season, comp)

add_event("other", "新歓ミーティング", today + timedelta(days=6), "18:00", None, "学生会館 201", "", "次期役員の相談", season, "")
add_event("other", "納会", today + timedelta(days=45), "19:00", None, "居酒屋（未定）", "", "", season, "")

# --- Attendance --------------------------------------------------------------
# Past events: 90% answered, 80% of those attending. Upcoming: 50% answered.
comments = ["少し遅れます", "前半だけ参加します", "車出せます", "用事があり欠席します", "試験のため"]
for eid, etype, d in events:
    past = d <= today
    for u in uids:
        if rng.random() >= (0.9 if past else 0.5):
            continue
        yes = rng.random() < (0.8 if past else 0.7)
        comment = rng.choice(comments) if rng.random() < 0.1 else ""
        cur.execute(q("insert into attendance (eid, uid, status, comment) values (%s, %s, %s, %s)"),
                    (eid, u, "yes" if yes else "no", comment))

# --- Results, goals, lineups (played matches only) ---------------------------
memos = ["", "前半の入りが良かった。", "後半に失点が続いた。要修正。", "セットプレーから2点。", "終盤まで集中できた。", ""]
for eid, etype, d in events:
    if etype != "match" or d > today:
        continue
    our = rng.choices([0, 1, 2, 3, 4, 5], weights=[1, 3, 4, 3, 2, 1])[0]
    opp = rng.choices([0, 1, 2, 3], weights=[4, 4, 2, 1])[0]
    our_1h, opp_1h = rng.randint(0, our), rng.randint(0, opp)
    pk_our = pk_opp = None
    if our == opp and rng.random() < 0.5:
        pk_our, pk_opp = (5, 4) if rng.random() < 0.5 else (3, 4)
    mvp = pick(goal_weight) if our > 0 else pick(assist_weight)
    cur.execute(q("insert into match_results (eid, our_1h, our_2h, opp_1h, opp_2h, our_pk, opp_pk, mvp_uid, memo) "
                  "values (%s, %s, %s, %s, %s, %s, %s, %s, %s)"),
                (eid, our_1h, our - our_1h, opp_1h, opp - opp_1h, pk_our, pk_opp, mvp, rng.choice(memos)))

    for i in range(our):
        scorer = pick(goal_weight)
        assist = pick(assist_weight, exclude=scorer) if rng.random() < 0.6 else None
        cur.execute(q("insert into goals (eid, side, scorer_uid, assist_uid, half, minute, note) "
                      "values (%s, 'our', %s, %s, %s, %s, %s)"),
                    (eid, scorer, assist, 1 if i < our_1h else 2, rng.randint(1, 45),
                     rng.choice(["", "", "", "", "PK", "ヘディング", "ミドル"])))
    for i in range(opp):
        cur.execute(q("insert into goals (eid, side, scorer_uid, assist_uid, half, minute, note) "
                      "values (%s, 'opp', null, null, %s, %s, '')"),
                    (eid, 1 if i < opp_1h else 2, rng.randint(1, 45)))

    # Lineup: 11 starters (at least one GK) and up to 5 subs from those attending.
    cur.execute(q("select uid from attendance where eid = %s and status = 'yes' and uid <> %s"), (eid, admin_uid))
    present = [r["uid"] for r in cur.fetchall()]
    gks = [u for u in present if pos_of[u] == "GK"]
    others = [u for u in present if pos_of[u] != "GK"]
    rng.shuffle(others)
    starters = (gks[:1] + others)[:11]
    subs = [u for u in present if u not in starters][:5]
    for u in starters:
        cur.execute(q("insert into lineups (eid, uid, role) values (%s, %s, 'starter')"), (eid, u))
    for u in subs:
        cur.execute(q("insert into lineups (eid, uid, role) values (%s, %s, 'sub')"), (eid, u))

# --- Posts and comments ------------------------------------------------------
posts = [
    # author, title, body, pinned, days ago, [(commenter, body), ...]
    (admin_uid, "リーグ戦 残り2試合！", "昇格争いは最終節までもつれそうです。\n練習の出席率を上げて、ベストメンバーで臨みましょう。\n車を出せる人は早めに教えてください。", 1, 3,
        [(uids[5], "日曜は車出せます！3人乗れます"), (uids[16], "得点王、狙います"), (uids[1], "了解です。GK練もう少しやりたいです")]),
    (uids[5], "ユニフォーム回収のお願い", "先週の試合で使った白ユニフォーム、まだ返してない人は次の練習で持ってきてください。洗濯済みでお願いします。", 0, 6,
        [(uids[10], "すみません、次回持っていきます")]),
    (uids[12], "新しいボール買いました", "練習用のボールを3つ補充しました。空気入れも倉庫に置いてあります。", 0, 10, []),
    (admin_uid, "納会の日程", "シーズン終わりの納会を企画中です。希望日があればコメントで教えてください。", 0, 14,
        [(uids[8], "12月第2週がいいです"), (uids[18], "平日夜より週末希望です"), (uids[3], "どっちでも参加します")]),
]
for uid, title, body, pinned, days_ago, replies in posts:
    cur.execute(q("insert into posts (uid, title, body, pinned, created_at) values (%s, %s, %s, %s, %s)"),
                (uid, title, body, pinned, ts(days_ago)))
    cur.execute(q("select max(pid) as m from posts"))
    pid = cur.fetchone()["m"]
    for i, (cuid, cbody) in enumerate(replies):
        cur.execute(q("insert into comments (pid, uid, body, created_at) values (%s, %s, %s, %s)"),
                    (pid, cuid, cbody, ts(days_ago, hour=21 + i)))

# --- Sample photos (last five played matches) --------------------------------
# Uses static/uploads/<eid>/sampleN.jpg if present; otherwise renders placeholders with Pillow.
try:
    from PIL import Image, ImageDraw
except ImportError:
    Image = None

palette = [((200, 16, 46), (255, 150, 150)), ((20, 90, 160), (150, 200, 255)), ((30, 130, 70), (160, 230, 180))]
n = 0
captions = ["試合前の集合写真", "ゴールシーン", "ハーフタイム", "試合後のミーティング", "応援に来てくれたOBと", "", ""]
for eid, _, d in [e for e in events if e[1] == "match" and e[2] <= today][-5:]:
    folder = os.path.join(config.BASE_DIR, "static", "uploads", str(eid))
    for k in range(3):
        name = f"sample{k + 1}.jpg"
        path = os.path.join(folder, name)
        if not os.path.exists(path) and Image is not None:
            os.makedirs(folder, exist_ok=True)
            c1, c2 = palette[n % len(palette)]
            img = Image.new("RGB", (800, 600))
            px = img.load()
            for y in range(600):
                t = y / 599
                col = tuple(int(c1[i] * (1 - t) + c2[i] * t) for i in range(3))
                for x in range(800):
                    px[x, y] = col
            dr = ImageDraw.Draw(img)
            dr.ellipse([330, 230, 470, 370], fill="#fff", outline="#111", width=6)
            dr.text((20, 560), f"sample photo {n + 1}", fill="#fff")
            img.save(path, quality=85)
        if os.path.exists(path):
            cur.execute(q("insert into photos (eid, uid, filename, caption, created_at) values (%s, %s, %s, %s, %s)"),
                        (eid, uids[(k + 3) % len(uids)], name,
                         rng.choice(captions), ts((today - d).days, 18)))
        n += 1

conn.commit()
cur.close()
conn.close()
print(f"seeded: {len(members) + 1 + len(alumni)} users, {len(events)} events, {len(posts)} posts")
print(f"login: admin@example.com / pass1234  (owner: {config.OWNER_EMAIL})")
