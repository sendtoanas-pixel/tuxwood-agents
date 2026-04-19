"""
TUXWOOD — Rifas (Operational Agent) — CLOUD VERSION
=====================================================
Morning check: 7:30 AM UAE  → Railway Cron: 30 3 * * *
Evening check: 6:00 PM UAE  → Railway Cron: 0 14 * * *

Command: python tuxwood_operational_agent.py morning
         python tuxwood_operational_agent.py evening
"""

import os
import sys
import json
import requests
import pandas as pd
from datetime import datetime, timedelta
from gmail_helper import fetch_report_from_gmail, read_sales_report

# ============================================================
# CONFIG
# ============================================================
WHATSAPP_TOKEN  = os.environ.get("WHATSAPP_TOKEN",  "")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID", "1127995510386994")
OWNER_NUMBER    = os.environ.get("OWNER_NUMBER",    "971569394846")
LOG_FILE        = "/
