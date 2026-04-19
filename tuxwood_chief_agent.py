"""
TUXWOOD — Anas (Chief Agent) — CLOUD VERSION
=============================================
Runs every morning at 8:00 AM UAE time.
Sends daily WhatsApp business brief to owner.

Railway Cron: 0 4 * * *  (4:00 AM UTC = 8:00 AM UAE)
Command: python tuxwood_chief_agent.py
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
FOLLOWUP_LOG    = "/tmp/tuxwood_purchase_log.json"
# ============================================================


def send_whatsapp(phone, message):
    url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"
    r = requests.post(url,
        headers={"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"},
        json={"messaging_product": "whatsapp", "to": phone, "type": "text", "text": {"body": message}})
    return r.status_code, r.json()


def load_followup_log():
    if os.path.exists(FOLLOWUP_LOG):
        with open(FOLLOWUP_LOG) as f:
            return json.load(f)
    return {}


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


def main():
    today     = datetime.now().strftime("%Y-%m-%d")
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    weekday   = datetime.now().strftime("%A")

    print("=" * 60)
    print("  TUXWOOD — Anas (Chief Agent) — CLOUD")
    print(f"  Date: {today} | Day: {weekday}")
    print("=" * 60)

    print("\n📧 Fetching sales report from Gmail...")
    report_file = fetch_report_from_gmail()

    sales_summary = "No sales report found today."
    total_orders  = 0
    total_revenue = 0
    top_products  = []

    if report_file:
        try:
            df = read_sales_report(report_file)
            df = df.dropna(subset=["Customer Name"])
            if "Mobile Number" in df.columns:
                df["Mobile Number"] = df["Mobile Number"].apply(format_phone)
            total_orders = len(df)
            if "Net Amount" in df.columns:
                total_revenue = df["Net Amount"].sum()
            if "Item Name" in df.columns:
                counter = Counter(df["Item Name"].dropna())
                top_products = counter.most_common(3)

            sales_summary = (
                f"📦 Orders: {total_orders}\n"
                f"💰 Revenue: AED {total_revenue:,.0f}\n"
            )
            if top_products:
                sales_summary += "🏆 Top sellers:\n"
                for p, c in top_products:
                    sales_summary += f"   • {p} ({c} units)\n"
        except Exception as e:
            sales_summary = f"Report found but error reading: {e}"

    log = load_followup_log()
    msgs_yesterday = sum(
        1 for v in log.values()
        if v.get("purchase_date") == yesterday
    )

    greeting = "Good morning" if datetime.now().hour < 12 else "Good afternoon"
    msg = (
        f"🌿 *Tuxwood Daily Brief — {today}*\n"
        f"{'━'*30}\n\n"
        f"*YESTERDAY'S SALES*\n"
        f"{sales_summary}\n"
        f"*FOLLOW-UPS SENT YESTERDAY*\n"
        f"📱 {msgs_yesterday} thank-you messages sent\n\n"
    )

    if weekday == "Monday":
        msg += "📅 *It's Monday — great day to review your weekly targets!*\n\n"

    msg += (
        f"{'━'*30}\n"
        f"🤖 Anas — Chief Agent\n"
        f"All agents running 24/7 ✅"
    )

    print("\n📤 Sending daily brief to owner...")
    code, resp = send_whatsapp(OWNER_NUMBER, msg)
    if code == 200:
        print("✅ Daily brief sent successfully!")
    else:
        print(f"❌ Failed to send: {resp}")


if __name__ == "__main__":
    main()
