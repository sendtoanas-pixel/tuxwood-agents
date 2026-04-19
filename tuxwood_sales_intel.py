"""
TUXWOOD — Sharook (Sales Intelligence Agent) — CLOUD VERSION
=============================================================
Analyzes yesterday's sales and sends smart WhatsApp report.

Railway Cron: 0 5 * * *  (5:00 AM UTC = 9:00 AM UAE)
Command: python tuxwood_sales_intel.py
"""

import os
import json
import requests
import pandas as pd
from datetime import datetime, timedelta
from collections import Counter
from gmail_helper import fetch_report_from_gmail, read_sales_report

# ============================================================
# CONFIG
# ============================================================
WHATSAPP_TOKEN  = os.environ.get("WHATSAPP_TOKEN",  "")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID", "1127995510386994")
OWNER_NUMBER    = os.environ.get("OWNER_NUMBER",    "971569394846")
# ============================================================


def send_whatsapp(phone, message):
    url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"
    r = requests.post(url,
        headers={"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application
