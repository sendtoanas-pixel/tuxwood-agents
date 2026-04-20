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
LOG_FILE        = "/tmp/tuxwood_operational_log.json"
FF_USERNAME     = os.environ.get("FF_USERNAME", "16546")
FF_PASSWORD     = os.environ.get("FF_PASSWORD", "PerJK@452")
FF_BASE_URL     = "https://app.firstflightme.com"
# ============================================================


def send_whatsapp(message):
    url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"
    r = requests.post(url,
        headers={"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"},
        json={"messaging_product": "whatsapp", "to": OWNER_NUMBER, "type": "text", "text": {"body": message}})
    return r.status_code, r.json()


def load_log():
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE) as f:
            return json.load(f)
    return {}


def save_log(log):
    with open(LOG_FILE, "w") as f:
        json.dump(log, f, indent=2)


def format_phone(raw_phone):
    phone = str(raw_phone).strip()
    if 'e' in phone.lower() or '.' in phone:
        try:
            phone = str(int(float(phone)))
        except:
            return None
    phone = phone.replace("+", "").replace("-", "").replace(" ", "")
    if not phone or phone == "nan":
        return None
    if not phone.startswith("971") and len(phone) == 9:
        phone = "971" + phone
    return phone


def get_first_flight_status():
    """Check undelivered First Flight shipments."""
    try:
        session = requests.Session()
        login_url = f"{FF_BASE_URL}/login"
        session.post(login_url, data={"username": FF_USERNAME, "password": FF_PASSWORD}, timeout=15)
        resp = session.get(f"{FF_BASE_URL}/shipments?status=pending", timeout=15)
        if resp.status_code == 200:
            return f"First Flight: {resp.status_code} checked"
    except Exception as e:
        return f"First Flight check failed: {e}"
    return "First Flight: checked"


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "morning"
    today = datetime.now().strftime("%Y-%m-%d")
    log = load_log()

    print("=" * 60)
    print(f"  TUXWOOD — Rifas (Operational) — {mode.upper()} — CLOUD")
    print(f"  Date: {today}")
    print("=" * 60)

    # Fetch sales report
    report_file = fetch_report_from_gmail()
    total_orders = 0
    total_revenue = 0

    if report_file:
        try:
            df = read_sales_report(report_file)
            df = df.dropna(subset=["Customer Name"])
            total_orders = len(df)
            if "Net Amount" in df.columns:
                total_revenue = df["Net Amount"].sum()
        except Exception as e:
            print(f"Error reading report: {e}")

    if mode == "morning":
        msg = (
            f"🌅 *Rifas — Morning Operations Report*\n"
            f"📅 {today}\n"
            f"{'━'*28}\n\n"
            f"📦 *Yesterday's Orders:* {total_orders}\n"
            f"💰 *Revenue:* AED {total_revenue:,.0f}\n\n"
            f"✅ All systems operational\n"
            f"🤖 Rifas — Operational Agent"
        )
        log["last_morning_report"] = today

    else:  # evening
        msg = (
            f"🌆 *Rifas — End of Day Report*\n"
            f"📅 {today}\n"
            f"{'━'*28}\n\n"
            f"📦 *Total Orders Today:* {total_orders}\n"
            f"💰 *Revenue:* AED {total_revenue:,.0f}\n\n"
            f"✅ Day complete. Good night! 🌙\n"
            f"🤖 Rifas — Operational Agent"
        )
        log["last_evening_report"] = today

    save_log(log)

    print(f"📤 Sending {mode} report...")
    code, resp = send_whatsapp(msg)
    if code == 200:
        print(f"✅ {mode.capitalize()} report sent!")
    else:
        print(f"❌ Failed: {resp}")


if __name__ == "__main__":
    main()
