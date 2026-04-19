"""
TUXWOOD — Shahan (Post-Purchase Follow-up Agent) — CLOUD VERSION
=================================================================
Cloud-ready: uses Gmail to fetch sales report PDF, env vars for credentials.

DAY 1 → Thank you message (same day)
DAY 3 → Google Review request

Deploy on Railway as a CRON job:
  Schedule: 15 23 * * *  (11:15 PM UAE = 7:15 PM UTC)
  Command:  python tuxwood_purchase_agent.py
"""

import pandas as pd
import requests
import json
import os
import sys
import time
from datetime import datetime, timedelta
from gmail_helper import fetch_report_from_gmail, read_sales_report as _read_file

# ============================================================
# CONFIG
# ============================================================
WHATSAPP_TOKEN     = os.environ.get("WHATSAPP_TOKEN",   "")
PHONE_NUMBER_ID    = os.environ.get("PHONE_NUMBER_ID",  "1127995510386994")
GOOGLE_REVIEW_LINK = "https://g.page/r/CWD2JXuNUfFNEAE/review"
LOG_FILE           = "/tmp/tuxwood_purchase_log.json"
# ============================================================


def load_log():
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_log(log):
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)


def format_phone(raw_phone):
    phone = str(raw_phone).strip()
    if 'e' in phone.lower() or '.' in phone:
        try:
            phone = str(int(float(phone)))
        except:
            return None
    phone = phone.replace("+", "").replace("-", "").replace(" ", "")
    if
