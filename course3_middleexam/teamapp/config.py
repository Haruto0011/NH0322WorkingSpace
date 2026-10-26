"""
Application settings. Edit this file for your team and environment.

Development: DB_KIND = "sqlite" (default, no setup required).
Production:  DB_KIND = "postgres", set POSTGRES_DSN, FORCE_HTTPS = True,
             DEMO_MODE = False, and replace SECRET_KEY / OWNER_PASSWORD.
"""
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# --- Team -------------------------------------------------------------------
TEAM_NAME = "MUDS FC"
TEAM_COLOR = "#c8102e"      # primary UI color (CSS hex)
CURRENT_SEASON = "2026"     # default season for new events; update each year

# --- Demo mode (for review / evaluation) -------------------------------------
# When True, anonymous visitors are treated as DEMO_USER_EMAIL and the login
# button signs in OWNER_EMAIL without a password (no login form is shown).
# Nothing in the UI indicates demo mode. Set False for real use.
DEMO_MODE = True
DEMO_USER_EMAIL = "admin@example.com"   # created by seed.py

# --- Owner account (created as admin by seed.py) -----------------------------
OWNER_NAME = "はると"
OWNER_EMAIL = "example@example.com"
OWNER_PASSWORD = "pass1234"             # change before production

# --- Security ----------------------------------------------------------------
SECRET_KEY = "6c424ac5d16d778bc1b14afa2c02b1c3"   # session signing key; change for production
FORCE_HTTPS = False                              # redirect http -> https (enable in production)

# --- Database ----------------------------------------------------------------
DB_KIND = "postgres"
POSTGRES_DSN = "host=localhost dbname=s2422113 user=s2422113 password=AnQJ7fNV"
SECRET_KEY = "hjfiow4809jcbbuudbndkncju59380809ujjchjfimwknfjjrohfirjfi3hihe5h9h5h9hu095htu835h"
FORCE_HTTPS = False      # まずは False のまま（URLが http:// なので）
DEMO_MODE = True

# --- Development server ------------------------------------------------------
DEV_PORT = 5050   # 5000 is taken by AirPlay Receiver on recent macOS
