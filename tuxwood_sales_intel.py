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
        headers={"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"},
        json={"messaging_product": "whatsapp", "to": phone, "type": "text", "text": {"body": message}})
    return r.status_code, r.json()


def main():
    today     = datetime.now().strftime("%Y-%m-%d")
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    print("=" * 60)
    print("  TUXWOOD — Sharook (Sales Intelligence) — CLOUD")
    print(f"  Date: {today}")
    print("=" * 60)

    print("\n📧 Fetching sales report from Gmail...")
    report_file = fetch_report_from_gmail()

    if not report_file:
        msg = (
            f"📊 *Sharook — Sales Report*\n"
            f"📅 {today}\n\n"
            f"⚠️ No sales report found in Gmail.\n"
            f"Please email the report with subject: 'sales report'"
        )
        send_whatsapp(OWNER_NUMBER, msg)
        return

    try:
        df = read_sales_report(report_file)
        df = df.dropna(subset=["Customer Name"])

        total_orders  = len(df)
        total_revenue = df["Net Amount"].sum() if "Net Amount" in df.columns else 0
        avg_order     = total_revenue / total_orders if total_orders > 0 else 0

        # Top products
        top_products = []
        if "Item Name" in df.columns:
            counter = Counter(df["Item Name"].dropna())
            top_products = counter.most_common(5)

        # Build report
        msg = (
            f"📊 *Sharook — Sales Intelligence Report*\n"
            f"📅 {yesterday}\n"
            f"{'━'*30}\n\n"
            f"*OVERVIEW*\n"
            f"📦 Total Orders: {total_orders}\n"
            f"💰 Total Revenue: AED {total_revenue:,.0f}\n"
            f"📈 Avg Order Value: AED {avg_order:,.0f}\n\n"
        )

        if top_products:
            msg += "*TOP SELLING PRODUCTS*\n"
            medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
            for i, (product, count) in enumerate(top_products):
                medal = medals[i] if i < len(medals) else "•"
                msg += f"{medal} {product} — {count} units\n"
            msg += "\n"

        # Smart insight
        if total_orders >= 10:
            msg += "🔥 *Strong day! Keep the momentum going.*\n"
        elif total_orders >= 5:
            msg += "✅ *Steady day. Consider a promotional push tomorrow.*\n"
        else:
            msg += "💡 *Slow day. Good time to run a campaign with Aslam.*\n"

        msg += f"\n🤖 Sharook — Sales Intelligence Agent"

        print(f"\n📊 Report ready: {total_orders} orders, AED {total_revenue:,.0f}")
        code, resp = send_whatsapp(OWNER_NUMBER, msg)
        if code == 200:
            print("✅ Sales report sent!")
        else:
            print(f"❌ Failed: {resp}")

    except Exception as e:
        print(f"❌ Error: {e}")
        send_whatsapp(OWNER_NUMBER, f"📊 Sharook: Error reading sales report — {e}")


if __name__ == "__main__":
    main()
