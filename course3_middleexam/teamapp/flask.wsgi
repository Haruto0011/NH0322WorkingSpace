# muds.gdl.jp にデプロイするときに使うファイル（手元で動かすときは使わない）
# 講義資料のとおり、石橋先生にこのファイルのパスを申請する
#   User ID: s0000001
#   Project Directory: /home/s0000001/teamapp/
#   WSGI Path: /home/s0000001/teamapp/flask.wsgi
import os
import sys

DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, DIR)

from app import app as application
