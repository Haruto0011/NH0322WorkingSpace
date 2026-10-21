"""
設定はすべてここにまとめる。
手元で動かす → DB_KIND = "sqlite"（このままでOK）
サーバにデプロイ → DB_KIND = "postgres" にして POSTGRES_DSN と FORCE_HTTPS を直す
"""
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# チーム名（画面の左上やタイトルに出る）
TEAM_NAME = "〇〇FC"

# セッション（ログイン状態）の暗号化に使う鍵。好きな文字列に変えてもよい
SECRET_KEY = "6c424ac5d16d778bc1b14afa2c02b1c3"

# "sqlite" : 手元のPCで動かすとき（インストール不要、team.db というファイルに保存される）
# "postgres" : muds.gdl.jp にデプロイするとき
DB_KIND = "sqlite"

SQLITE_PATH = os.path.join(BASE_DIR, "team.db")

# デプロイ時に自分のものへ書き換える（講義資料の psycopg2.connect(...) と同じ書式）
POSTGRES_DSN = "host=localhost dbname=s0000001 user=s0000001 password=XXXXXX"

# サーバでは True にすると http でアクセスされても https に飛ばす（講義資料の before_request と同じ）
FORCE_HTTPS = False
