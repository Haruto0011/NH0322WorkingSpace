"""
お試しデータを入れる（任意）:  python seed.py
空のDBにだけ入れる。メンバー6人・予定5件・適当な出欠が入る。
全員パスワードは pass1234
  管理者: admin@example.com
  選手  : tanaka@example.com など
"""
from datetime import date, timedelta

from werkzeug.security import generate_password_hash

import db

conn = db.get_conn()
cur = conn.cursor()
q = db.convert  # %s → ? の変換（SQLiteのとき）

cur.execute(q("select count(*) as c from users"))
if cur.fetchone()["c"] > 0:
    print("すでにユーザが登録されているので何もしません。")
    conn.close()
    raise SystemExit

pw = generate_password_hash("pass1234", method="pbkdf2:sha256")

users = [
    # (名前, email, role, 背番号, ポジション)
    ("監督",   "admin@example.com",  "admin",  None, None),
    ("田中",   "tanaka@example.com", "member", 1,  "GK"),
    ("鈴木",   "suzuki@example.com", "member", 4,  "DF"),
    ("佐藤",   "sato@example.com",   "member", 8,  "MF"),
    ("高橋",   "takahashi@example.com", "member", 10, "MF"),
    ("伊藤",   "ito@example.com",    "member", 9,  "FW"),
]
for name, email, role, number, pos in users:
    cur.execute(q("insert into users (uname, email, pw, role, number, position) "
                  "values (%s, %s, %s, %s, %s, %s)"),
                (name, email, pw, role, number, pos))

today = date.today()
events = [
    # (種別, タイトル, 日付, 開始, 終了, 場所, 相手, メモ)
    ("practice", "通常練習", today - timedelta(days=5), "19:00", "21:00", "〇〇グラウンド", "", ""),
    ("practice", "通常練習", today + timedelta(days=1), "19:00", "21:00", "〇〇グラウンド", "", "ビブス持参"),
    ("match",    "練習試合 vs △△FC", today + timedelta(days=4), "10:00", "12:00", "□□公園サッカー場", "△△FC", "集合 9:15\n白ユニフォーム"),
    ("practice", "通常練習", today + timedelta(days=8), "19:00", "21:00", "〇〇グラウンド", "", ""),
    ("other",    "新歓ミーティング", today + timedelta(days=12), "18:00", None, "学生会館 201", "", "次期役員の相談"),
]
for etype, title, d, st, et, place, opp, note in events:
    cur.execute(q("insert into events (etype, title, event_date, start_time, end_time, place, opponent, note, created_by) "
                  "values (%s, %s, %s, %s, %s, %s, %s, %s, 1)"),
                (etype, title, d.isoformat(), st, et, place, opp, note))

# 出欠を適当に入れる
cur.execute(q("select uid from users order by uid"))
uids = [r["uid"] for r in cur.fetchall()]
cur.execute(q("select eid from events order by eid"))
eids = [r["eid"] for r in cur.fetchall()]

pattern = ["yes", "yes", "no", "yes", None, "yes"]  # 6人分（None は未回答）
for i, eid in enumerate(eids[:3]):
    for j, uid in enumerate(uids):
        status = pattern[(i + j) % len(pattern)]
        if status:
            comment = "少し遅れます" if (i + j) % 4 == 0 else ""
            cur.execute(q("insert into attendance (eid, uid, status, comment) values (%s, %s, %s, %s)"),
                        (eid, uid, status, comment))

conn.commit()
cur.close()
conn.close()
print("OK: お試しデータを入れました。admin@example.com / pass1234 でログインできます。")
