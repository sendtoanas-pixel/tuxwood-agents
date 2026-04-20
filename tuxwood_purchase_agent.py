"""
TUXWOOD — Shahan (Post-Purchase Follow-up Agent) — CLOUD VERSION
=================================================================
Runs every 15 minutes. Checks Gmail for NEW (unread) sales report emails.
Processes immediately when a new report arrives — no fixed schedule needed.

DAY 1 → Thank you message (sent as soon as sales report email is received)
DAY 3 → Google Review request (checked on every run)

Deploy on Railway as a CRON job:
  Schedule: */15 * * * *  (every 15 minutes, all day)
  Command:  python tuxwood_purchase_agent.py
"""

import pandas as pd
import requests
import json
import os
import sys
import time
from datetime import datetime, timedelta
from gmail_helper import fetch_new_report_from_gmail, read_sales_report as _read_file

# ============================================================
# CONFIG — from Railway environment variables
# ============================================================
WHATSAPP_TOKEN    = os.environ.get("WHATSAPP_TOKEN",   "")
PHONE_NUMBER_ID   = os.environ.get("PHONE_NUMBER_ID",  "1127995510386994")
GOOGLE_REVIEW_LINK = "https://g.page/r/CWD2JXuNUfFNEAE/review"
LOG_FILE          = "/tmp/tuxwood_purchase_log.json"
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
    if not phone or phone == "nan":
        return None
    if not phone.startswith("971") and len(phone) == 9:
        phone = "971" + phone
    return phone


def read_sales_report(file_path):
    df = _read_file(file_path)  # handles both PDF and Excel
    df = df.dropna(subset=["Customer Name"])
    if "Invoice Date" in df.columns:
        df = df.dropna(subset=["Invoice Date"])
    if "Mobile Number" in df.columns:
        df["Mobile Number"] = df["Mobile Number"].apply(format_phone)
        df = df[df["Mobile Number"].notna()]
    return df


def send_whatsapp(phone, message):
    url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"}
    payload = {
        "messaging_product": "whatsapp",
        "to": phone,
        "type": "text",
        "text": {"body": message}
    }
    r = requests.post(url, headers=headers, json=payload)
    return r.status_code, r.json()


def generate_thankyou(name, items):
    display_name = name if not name.replace(" ", "").isdigit() else "Valued Customer"
    return (
        f"Hi {display_name}! 🌿\n\n"
        f"Thanks for choosing Tuxwood. Let's begin your fragrance journey with us ✨\n\n"
        f"شكراً لاختيارك تكسوود. لنبدأ رحلتك العطرية معنا ✨"
    )


def generate_review_request(name):
    display_name = name if not name.replace(" ", "").isdigit() else "Valued Customer"
    return (
        f"Hi {display_name},\n\n"
        f"We hope you're enjoying your Tuxwood fragrance! 🌿\n"
        f"If you loved the experience, we'd be truly grateful if you could share a quick Google review — it helps us discover new creations.\n\n"
        f"👉 {GOOGLE_REVIEW_LINK}\n\n"
        f"Tuxwood Perfumes Team ✨\n\n"
        f"---\n"
        f"مرحباً {display_name}،\n\n"
        f"نأمل أنك تستمتع بعطرك من تكسوود! 🌿\n"
        f"إذا أعجبك العطر، سيسعدنا كثيراً لو تتركت لنا تقييماً سريعاً على Google.\n\n"
        f"👉 {GOOGLE_REVIEW_LINK}\n\n"
        f"فريق تكسوود للعطور ✨"
    )


def run_purchase_agent():
    today    = datetime.now().strftime("%Y-%m-%d")
    now_str  = datetime.now().strftime("%Y-%m-%d %H:%M")
    day3     = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")

    print("=" * 60)
    print("  TUXWOOD — Shahan (Post-Purchase Agent) — CLOUD")
    print(f"  {now_str}")
    print("=" * 60)

    log = load_log()
    pending = []

    # ── CHECK FOR NEW (UNREAD) SALES REPORT EMAIL ─────────────
    print("\n📧 Checking Gmail for new sales report...")
    result = fetch_new_report_from_gmail(unread_only=True)

    if result:
        report_file, email_uid = result

        # Skip if we already processed this email UID
        if log.get("last_processed_email_uid") == email_uid:
            print(f"⚠️  Email UID {email_uid} already processed. Skipping.")
        else:
            print(f"✅ New report found (email UID: {email_uid})")
            try:
                df = read_sales_report(report_file)
                print(f"✅ {len(df)} customer purchases loaded")

                for _, row in df.iterrows():
                    name  = str(row.get("Customer Name", "Valued Customer")).strip()
                    phone = str(row.get("Mobile Number", "")).strip()
                    items = str(row.get("Items", "your fragrance")).strip()
                    key   = f"{phone}_{today}"
                    if key in log and log[key].get("day1_sent"):
                        continue
                    pending.append({
                        "type": "day1_thankyou",
                        "name": name, "phone": phone,
                        "items": items, "date": today, "key": key
                    })

                # Remember we processed this email
                log["last_processed_email_uid"] = email_uid

            except Exception as e:
                print(f"❌ Error reading report: {e}")
    else:
        print("✅ No new sales report email. Checking Day 3 reviews only...")

    # ── DAY 3 — GOOGLE REVIEW (runs every time) ───────────────
    for phone_key, entry in log.items():
        if isinstance(entry, dict):
            if entry.get("purchase_date") == day3 and not entry.get("day3_sent"):
                pending.append({
                    "type": "day3_review",
                    "name": entry["name"], "phone": entry["phone"],
                    "items": entry.get("items", ""), "date": day3, "key": phone_key
                })

    if not pending:
        print("\n✅ Nothing to send right now.")
        save_log(log)
        return

    # ── SEND MESSAGES ─────────────────────────────────────────
    print(f"\n⚡ Sending {len(pending)} messages...")
    sent = 0
    failed = 0

    for item in pending:
        phone = item["phone"]
        name  = item["name"]
        mtype = item["type"]
        key   = item["key"]

        msg = generate_thankyou(name, item["items"]) if mtype == "day1_thankyou" else generate_review_request(name)

        try:
            status_code, api_resp = send_whatsapp(phone, msg)
            if status_code == 200:
                print(f"  ✅ Sent [{mtype}] → {name} ({phone})")
                sent += 1
                if key not in log:
                    log[key] = {"name": name, "phone": phone, "items": item.get("items", ""), "purchase_date": item["date"]}
                log[key][f"{mtype.split('_')[0]}_sent"] = True
                log[key][f"{mtype.split('_')[0]}_sent_at"] = datetime.now().isoformat()
            else:
                print(f"  ❌ Failed [{mtype}] → {name} | {api_resp}")
                failed += 1
        except Exception as e:
            print(f"  ❌ Error sending to {name}: {e}")
            failed += 1

    save_log(log)
    print(f"\n{'='*60}")
    print(f"  SUMMARY: {sent} sent, {failed} failed")
    print("=" * 60)


if __name__ == "__main__":
    run_purchase_agent()
