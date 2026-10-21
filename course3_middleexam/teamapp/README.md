# サッカーチーム管理サイト（Phase 1 モック）

Flask + SQLite（手元）/ PostgreSQL（サーバ）+ Bootstrap

## 手元で動かす（VS Code のターミナルで）

```bash
cd teamapp
python3 -m venv .venv
source .venv/bin/activate        # ← ターミナル左端に (.venv) と出ればOK
pip install -r requirements.txt
python init_db.py                # テーブルを作る（最初の1回だけ）
python seed.py                   # お試しデータを入れる（任意）
python app.py                    # → http://127.0.0.1:5000 をブラウザで開く
```

お試しデータを入れた場合は `admin@example.com` / `pass1234` でログインできる（管理者）。
選手側の見え方は `tanaka@example.com` / `pass1234` など。

お試しデータを入れずに自分で登録する場合、**最初に登録した人が自動で管理者**になる。

## ファイル構成

```
teamapp/
├── app.py               Flask本体（ルート＝URLごとの処理）
├── db.py                DBアクセス（SQLite/PostgreSQLの差を吸収）
├── config.py            設定（チーム名・DB・鍵）
├── init_db.py           テーブル作成
├── seed.py              お試しデータ
├── schema_sqlite.sql    テーブル定義（手元用）
├── schema_postgres.sql  テーブル定義（サーバ用）
├── flask.wsgi           サーバ用（講義資料の wsgi と同じ役割）
├── templates/           画面（Jinja2 テンプレート）
│   ├── layout.html      共通レイアウト（ナビバー・Bootstrap読込）
│   ├── _macros.html     使い回す部品（バッジ・予定の行）
│   ├── index.html       ホーム
│   ├── events.html      予定一覧
│   ├── event_detail.html 予定詳細・出欠回答
│   ├── event_form.html  予定の追加/編集（管理者）
│   ├── members.html     メンバー一覧
│   ├── profile.html     プロフィール編集
│   ├── login.html / regist.html
└── static/css/style.css
```

## サーバ(muds.gdl.jp)にデプロイするとき

1. `config.py` を直す: `DB_KIND = "postgres"`, `POSTGRES_DSN` を自分のもの, `FORCE_HTTPS = True`
2. サーバに ssh して psql で `schema_postgres.sql` を実行
3. Cyberduck で `teamapp/` フォルダごとアップロード（`.venv` と `team.db` は不要）
4. 講義資料どおり、`flask.wsgi` のパスを石橋先生へ申請
