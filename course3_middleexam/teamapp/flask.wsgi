# mod_wsgi entry point. Register this file's path with the server administrator.
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app as application  # noqa: E402
