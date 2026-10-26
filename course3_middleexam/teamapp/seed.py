"""
お試しデータを入れる（任意）:  python seed.py
空のDBにだけ入れる。入るもの：
  ・メンバー21人（監督＋選手19人＋自分、身長・体重・生年月日つき）
  ・2025シーズン：試合6件（結果入り）
  ・2026シーズン：毎週土曜の練習（過去28週＋今後4週）、試合13件（過去10件は結果入り）、その他の予定
  ・出欠と得点・アシスト・MVP（乱数で生成。毎回同じ内容になる）
全員パスワードは pass1234
  管理者: admin@example.com
  選手  : tanaka@example.com など（ローマ字 + @example.com）
"""
import random
from datetime import date, timedelta

from werkzeug.security import generate_password_hash

import config
import db

rng = random.Random(2026)   # 乱数の種を固定 → 何度実行しても同じデータになる

conn = db.get_conn()
cur = conn.cursor()
q = db.convert  # %s → ? の変換（SQLiteのとき）

cur.execute(q("select count(*) as c from users"))
if cur.fetchone()["c"] > 0:
    print("すでにユーザが登録されているので何もしません。")
    conn.close()
    raise SystemExit

pw = generate_password_hash("pass1234", method="pbkdf2:sha256")
today = date.today()
season = config.CURRENT_SEASON
prev_season = str(int(season) - 1)

# ---------------------------------------------------------------
# メンバー
# ---------------------------------------------------------------
members = [
    # (名前, ローマ字, role, 背番号, ポジション, 身長, 体重, 生年月日, 利き足, ひとこと)
    ("監督",   "admin",     "admin",  None, None, None, None, None,         None, "今年こそ昇格！"),
    ("田中",   "tanaka",    "member", 1,  "GK", 183, 78, "2003-04-12", "右", "キャプテン。ビッグセーブで流れを引き寄せます"),
    ("山本",   "yamamoto",  "member", 21, "GK", 178, 74, "2005-11-03", "右", ""),
    ("鈴木",   "suzuki",    "member", 2,  "DF", 175, 70, "2004-01-25", "右", ""),
    ("渡辺",   "watanabe",  "member", 3,  "DF", 180, 75, "2003-09-08", "左", "左SB。クロスが武器"),
    ("中村",   "nakamura",  "member", 4,  "DF", 182, 77, "2002-06-30", "右", "キャプテン"),
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
uids, pos_of = [], {}
for name, romaji, role, number, pos, h, w, bd, foot, intro in members:
    cur.execute(q("insert into users (uname, email, pw, role, number, position, height_cm, weight_kg, birthdate, foot, intro, captain) "
                  "values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"),
                (name, f"{romaji}@example.com", pw, role, number, pos, h, w, bd, foot, intro, 1 if romaji == "tanaka" else 0))
cur.execute(q("select uid, position from users order by uid"))
for r in cur.fetchall():
    uids.append(r["uid"])
    pos_of[r["uid"]] = r["position"]
admin_uid = uids[0]
players = uids[1:]

# 自分（オーナー）のアカウント：config.py の内容で管理者として作る（選手データや出欠には含めない）
cur.execute(q("insert into users (uname, email, pw, role) values (%s, %s, %s, 'admin')"),
            (config.OWNER_NAME, config.OWNER_EMAIL.lower(), generate_password_hash(config.OWNER_PASSWORD, method="pbkdf2:sha256")))

# 得点者・アシストの選ばれやすさ（FW > MF > DF、GK は得点しない）
goal_weight = {"GK": 0, "DF": 1, "MF": 3, "FW": 6}
assist_weight = {"GK": 0, "DF": 2, "MF": 5, "FW": 3}


def pick(weights, exclude=None):
    cands = [u for u in players if weights[pos_of[u]] > 0 and u != exclude]
    return rng.choices(cands, weights=[weights[pos_of[u]] for u in cands])[0]


# ---------------------------------------------------------------
# 予定
# ---------------------------------------------------------------
opponents = ["東京蹴球団", "FC PHOENIX", "杉並FC", "練馬ユナイテッド", "渋谷SC", "品川FC",
             "三鷹クラブ", "調布FC", "世田谷FC", "大田ユナイテッド", "北区FC", "足立SC"]
grounds = ["代々木公園サッカー場", "みらい平グラウンド", "駒沢第二球技場", "夢の島競技場", "多摩川緑地G"]


def add_event(etype, title, d, st, et, place, opp, note, season_, comp):
    cur.execute(q("insert into events (etype, title, event_date, start_time, end_time, place, opponent, note, "
                  "season, competition, created_by) values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"),
                (etype, title, d.isoformat(), st, et, place, opp, note, season_, comp, admin_uid))
    cur.execute(q("select max(eid) as m from events"))
    return cur.fetchone()["m"]


events = []   # (eid, etype, date)

# --- 前シーズン：試合6件（昨年の 4〜12 月あたり） ---
for i in range(6):
    d = today - timedelta(days=560 - i * 40)
    opp = opponents[i]
    comp = "東京都リーグ" if i < 4 else "東京カップ"
    eid = add_event("match", f"リーグ戦 vs {opp}" if comp == "東京都リーグ" else f"東京カップ vs {opp}",
                    d, "14:00", "16:00", rng.choice(grounds), opp, "", prev_season, comp)
    events.append((eid, "match", d))

# --- 今シーズン：毎週土曜の練習（28週前〜4週後） ---
last_sat = today - timedelta(days=(today.weekday() - 5) % 7)   # 直近の土曜（今日が土曜なら今日）
for w in range(-28, 5):
    d = last_sat + timedelta(weeks=w)
    note = rng.choice(["", "", "", "ビブス持参", "雨天時は中止連絡します", "終了後ミーティングあり"])
    eid = add_event("practice", "通常練習", d, "19:00", "21:00", "〇〇グラウンド", "", note, season, "")
    events.append((eid, "practice", d))

# --- 今シーズン：試合13件（過去10件、今後3件） ---
match_plan = [
    # (今日から何日前(+なら後), 大会, 相手)
    (-180, "練習試合", "三鷹クラブ"),
    (-160, "東京都リーグ", "東京蹴球団"),
    (-140, "東京都リーグ", "FC PHOENIX"),
    (-120, "東京都リーグ", "杉並FC"),
    (-100, "東京カップ", "練馬ユナイテッド"),
    (-80,  "東京都リーグ", "渋谷SC"),
    (-60,  "練習試合", "品川FC"),
    (-40,  "東京カップ", "調布FC"),
    (-19,  "東京都リーグ", "世田谷FC"),
    (-12,  "東京都リーグ", "大田ユナイテッド"),
    (4,    "練習試合", "北区FC"),
    (11,   "東京カップ", "足立SC"),
    (25,   "東京都リーグ", "三鷹クラブ"),
]
for offset, comp, opp in match_plan:
    d = today + timedelta(days=offset)
    title = {"東京都リーグ": f"リーグ戦 vs {opp}", "東京カップ": f"東京カップ vs {opp}"}.get(comp, f"練習試合 vs {opp}")
    note = rng.choice(["", "集合は開始45分前", "白ユニフォーム", "車出せる人は監督まで"])
    eid = add_event("match", title, d, "13:50", "15:40", rng.choice(grounds), opp, note, season, comp)
    events.append((eid, "match", d))

# --- その他 ---
eid = add_event("other", "新歓ミーティング", today + timedelta(days=6), "18:00", None, "学生会館 201", "", "次期役員の相談", season, "")
events.append((eid, "other", today + timedelta(days=6)))
eid = add_event("other", "納会", today + timedelta(days=45), "19:00", None, "居酒屋（未定）", "", "", season, "")
events.append((eid, "other", today + timedelta(days=45)))

# ---------------------------------------------------------------
# 出欠（終わった予定は9割が回答・うち8割が出席。今後の予定は半分くらいが回答済み）
# ---------------------------------------------------------------
comments = ["少し遅れます", "前半だけ参加します", "車出せます", "用事があり欠席します", "試験のため"]
for eid, etype, d in events:
    past = d <= today
    for u in uids:
        if not (rng.random() < (0.9 if past else 0.5)):
            continue                                        # 未回答
        yes = rng.random() < (0.8 if past else 0.7)
        comment = rng.choice(comments) if rng.random() < 0.1 else ""
        cur.execute(q("insert into attendance (eid, uid, status, comment) values (%s, %s, %s, %s)"),
                    (eid, u, "yes" if yes else "no", comment))

# ---------------------------------------------------------------
# 試合結果と得点（終わった試合だけ）
# ---------------------------------------------------------------
memos = ["", "前半の入りが良かった。", "後半に失点が続いた。要修正。", "セットプレーから2点。", "終盤まで集中できた。", ""]
for eid, etype, d in events:
    if etype != "match" or d > today:
        continue
    our = rng.choices([0, 1, 2, 3, 4, 5], weights=[1, 3, 4, 3, 2, 1])[0]
    opp = rng.choices([0, 1, 2, 3], weights=[4, 4, 2, 1])[0]
    our_1h = rng.randint(0, our)
    opp_1h = rng.randint(0, opp)
    pk_our = pk_opp = None
    if our == opp and rng.random() < 0.5:   # 引き分けの半分はPK戦
        pk_our, pk_opp = (5, 4) if rng.random() < 0.5 else (3, 4)
    mvp = pick(goal_weight) if our > 0 else pick(assist_weight)
    cur.execute(q("insert into match_results (eid, our_1h, our_2h, opp_1h, opp_2h, our_pk, opp_pk, mvp_uid, memo) "
                  "values (%s, %s, %s, %s, %s, %s, %s, %s, %s)"),
                (eid, our_1h, our - our_1h, opp_1h, opp - opp_1h, pk_our, pk_opp, mvp, rng.choice(memos)))

    # 自チームの得点
    for i in range(our):
        half = 1 if i < our_1h else 2
        scorer = pick(goal_weight)
        assist = pick(assist_weight, exclude=scorer) if rng.random() < 0.6 else None
        note = rng.choice(["", "", "", "", "PK", "ヘディング", "ミドル"])
        cur.execute(q("insert into goals (eid, side, scorer_uid, assist_uid, half, minute, note) "
                      "values (%s, %s, %s, %s, %s, %s, %s)"),
                    (eid, "our", scorer, assist, half, rng.randint(1, 45), note))
    # 相手の得点
    for i in range(opp):
        half = 1 if i < opp_1h else 2
        cur.execute(q("insert into goals (eid, side, scorer_uid, assist_uid, half, minute, note) "
                      "values (%s, %s, %s, %s, %s, %s, %s)"),
                    (eid, "opp", None, None, half, rng.randint(1, 45), ""))

# ---------------------------------------------------------------
# 出場メンバー（終わった試合：出席者から先発11人＋控え）
# ---------------------------------------------------------------
for eid, etype, d in events:
    if etype != "match" or d > today:
        continue
    cur.execute(q("select uid from attendance where eid = %s and status = 'yes' and uid <> %s"), (eid, admin_uid))
    present = [r["uid"] for r in cur.fetchall()]
    # GK を1人は入れる
    gks = [u for u in present if pos_of[u] == "GK"]
    others = [u for u in present if pos_of[u] != "GK"]
    rng.shuffle(others)
    starters = (gks[:1] + others)[:11]
    subs = [u for u in present if u not in starters][:5]
    for u in starters:
        cur.execute(q("insert into lineups (eid, uid, role) values (%s, %s, 'starter')"), (eid, u))
    for u in subs:
        cur.execute(q("insert into lineups (eid, uid, role) values (%s, %s, 'sub')"), (eid, u))

# ---------------------------------------------------------------
# 投稿とコメント
# ---------------------------------------------------------------
from datetime import datetime
def ts(days_ago, hour=20):
    return (datetime.combine(today, datetime.min.time()) - timedelta(days=days_ago)).replace(hour=hour).strftime("%Y-%m-%d %H:%M:%S")

posts = [
    # (投稿者, タイトル, 本文, 固定, 何日前, [(コメント者, 本文), ...])
    (admin_uid, "リーグ戦 残り2試合！", "昇格争いは最終節までもつれそうです。\n練習の出席率を上げて、ベストメンバーで臨みましょう。\n車を出せる人は早めに教えてください。", 1, 3,
        [(uids[5], "日曜は車出せます！3人乗れます"), (uids[16], "得点王、狙います"), (uids[1], "了解です。GK練もう少しやりたいです")]),
    (uids[5], "ユニフォーム回収のお願い", "先週の試合で使った白ユニフォーム、まだ返してない人は次の練習で持ってきてください。洗濯済みでお願いします。", 0, 6,
        [(uids[10], "すみません、次回持っていきます")]),
    (uids[12], "新しいボール買いました", "練習用のボールを3つ補充しました。空気入れも倉庫に置いてあります。", 0, 10, []),
    (admin_uid, "納会の日程", "シーズン終わりの納会を企画中です。希望日があればコメントで教えてください。", 0, 14,
        [(uids[8], "12月第2週がいいです"), (uids[18], "平日夜より週末希望です"), (uids[3], "どっちでも参加します")]),
]
for uid, title, body, pinned, days_ago, comments_ in posts:
    cur.execute(q("insert into posts (uid, title, body, pinned, created_at) values (%s, %s, %s, %s, %s)"),
                (uid, title, body, pinned, ts(days_ago)))
    cur.execute(q("select max(pid) as m from posts"))
    pid = cur.fetchone()["m"]
    for i, (cuid, cbody) in enumerate(comments_):
        cur.execute(q("insert into comments (pid, uid, body, created_at) values (%s, %s, %s, %s)"),
                    (pid, cuid, cbody, ts(days_ago, hour=21 + i)))

# ---------------------------------------------------------------
# 写真（直近2試合に3枚ずつ）
#   static/uploads/<eid>/sample1〜3.jpg があればそれを登録する。
#   無ければ Pillow でサンプル画像を作る（Pillow も無ければ写真なし）
# ---------------------------------------------------------------
import os
photo_events = [e for e in events if e[1] == "match" and e[2] <= today][-2:]   # 直近2試合
try:
    from PIL import Image, ImageDraw
except ImportError:
    Image = None
palette = [((200, 16, 46), (255, 150, 150)), ((20, 90, 160), (150, 200, 255)), ((30, 130, 70), (160, 230, 180))]
n = 0
for eid, _, d in photo_events:
    folder = os.path.join(config.BASE_DIR, "static", "uploads", str(eid))
    for k in range(3):
        name = f"sample{k + 1}.jpg"
        path = os.path.join(folder, name)
        if not os.path.exists(path) and Image is not None:
            os.makedirs(folder, exist_ok=True)
            c1, c2 = palette[n % len(palette)]
            img = Image.new("RGB", (800, 600))
            px = img.load()
            for y in range(600):                      # 上下のグラデーション
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
                        (eid, uids[(k + 3) % len(uids)], name, rng.choice(["", "試合前の集合写真", "ゴールシーン", ""]), ts((today - d).days, 18)))
        n += 1

conn.commit()
cur.close()
conn.close()
print(f"OK: お試しデータを入れました（メンバー{len(members)}人・予定{len(events)}件・投稿{len(posts)}件）。")
print("    admin@example.com / pass1234 でログインできます（選手は tanaka@example.com など）。")
