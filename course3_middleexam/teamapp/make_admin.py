"""
Grant administrator rights to a user.

    python make_admin.py user@example.com
"""
import sys

import db

if len(sys.argv) != 2:
    print("usage: python make_admin.py <email>")
    raise SystemExit(1)

email = sys.argv[1].strip().lower()
conn = db.get_conn()
cur = conn.cursor()
cur.execute(db.convert("select uid, uname, role from users where email = %s"), (email,))
user = cur.fetchone()

if user is None:
    print(f"user not found: {email}")
elif user["role"] == "admin":
    print(f"{user['uname']} is already an admin")
else:
    cur.execute(db.convert("update users set role = 'admin' where uid = %s"), (user["uid"],))
    conn.commit()
    print(f"{user['uname']} is now an admin (takes effect on next login)")

cur.close()
conn.close()
