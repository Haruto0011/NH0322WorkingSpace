"""
指定したメールアドレスのユーザを管理者にする:  python make_admin.py you@example.com
（サーバでも同じコマンドで使える）
"""
import sys

import db

if len(sys.argv) != 2:
    print("使い方: python make_admin.py メールアドレス")
    raise SystemExit(1)

email = sys.argv[1].strip().lower()

conn = db.get_conn()
cur = conn.cursor()
cur.execute(db.convert("select uid, uname, role from users where email = %s"), (email,))
user = cur.fetchone()

if user is None:
    print(f"見つかりません: {email}")
elif user["role"] == "admin":
    print(f"{user['uname']} はすでに管理者です。")
else:
    cur.execute(db.convert("update users set role = 'admin' where uid = %s"), (user["uid"],))
    conn.commit()
    print(f"OK: {user['uname']} を管理者にしました。ログインし直すと反映されます。")

cur.close()
conn.close()
