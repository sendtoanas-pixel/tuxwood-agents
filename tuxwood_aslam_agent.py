"""
TUXWOOD — Aslam (Retention Agent) — CLOUD VERSION
===================================================
Reads master contact list from Google Sheets.
Sends segment-based WhatsApp retention messages weekly.
Requires owner approval via Ozani before sending.

Segments:
  VIP            → Exclusive loyalty message
  VIP, Reactive  → Welcome back VIP message
  VIP, Non-active→ Re-engage VIP message
  Active/Regular → Appreciation message
  Reactive       → Welcome back message
  Non-active     → We miss you message

Railway Cron: 0 6 * * 0  (6:00 AM UTC = 10:00 AM UAE — every Sunday)
Command: python tuxwood_aslam_agent.py
"""

import os
import json
import requests
import gspread
from datetime import datetime
from google.oauth2.service_account import Credentials

# ============================================================
# CONFIG
# ============================================================
WHATSAPP_TOKEN     = os.environ.get("WHATSAPP_TOKEN",  "")
PHONE_NUMBER_ID    = os.environ.get("PHONE_NUMBER_ID", "1127995510386994")
OWNER_NUMBER       = os.environ.get("OWNER_NUMBER",    "971569394846")
OZANI_URL          = os.environ.get("OZANI_URL", "https://tuxwood-agents-production.up.railway.app")
GOOGLE_CREDENTIALS = os.environ.get("GOOGLE_CREDENTIALS", "")
SHEET_ID           = "1jJId7XyKsKLpADvtIha83L5-Cy74zFe9"
LOG_FILE           = "/tmp/aslam_retention_log.json"

TARGET_COUNTRIES   = ["UAE"]
TARGET_SEGMENTS    = ["VIP", "VIP, Reactive", "VIP, Non-active", "Active/Regular", "Reactive", "Non-active"]
MAX_PER_SEGMENT    = 50
# ============================================================


def load_log():
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE) as f:
            return json.load(f)
    return {}


def save_log(log):
    with open(LOG_FILE, "w") as f:
        json.dump(log, f, indent=2)


def connect_google_sheet():
    try:
        creds_dict = json.loads(GOOGLE_CREDENTIALS)
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets.readonly",
            "https://www.googleapis.com/auth/drive.readonly"
        ]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        client = gspread.authorize(creds)
        sheet = client.open_by_key(SHEET_ID).sheet1
        print("✅ Connected to Google Sheets")
        return sheet
    except Exception as e:
        print(f"❌ Google Sheets connection error: {e}")
        return None


def fetch_contacts(sheet):
    try:
        records = sheet.get_all_records()
        print(f"✅ Fetched {len(records)} contacts from Google Sheets")
        return records
    except Exception as e:
        print(f"❌ Error fetching contacts: {e}")
        return []


def generate_message(name, segment):
    display_name = name.strip().title() if name and not name.strip().replace(" ", "").isdigit() else "Valued Customer"

    if "VIP" in segment and "Non-active" in segment:
        return (
            f"Hi {display_name}! 🌿\n\n"
            f"We've been thinking of you — it's been a while since your last visit to Tuxwood.\n\n"
            f"As one of our most valued VIP customers, we'd love to welcome you back. "
            f"We have exciting new fragrances waiting for you! 🌸\n\n"
            f"WhatsApp us anytime — we're here for you.\n"
            f"Tuxwood Perfumes ✨\n\n"
            f"---\n"
            f"مرحباً {display_name}! 🌿\n"
            f"لقد افتقدناك — نتمنى أن تعود لزيارتنا قريباً.\n"
            f"لدينا عطور جديدة رائعة تنتظرك! ✨"
        )
    elif "VIP" in segment and "Reactive" in segment:
        return (
            f"Hi {display_name}! 🌿\n\n"
            f"Welcome back! We're so glad you're with us again. 🌸\n\n"
            f"As our VIP customer, your loyalty means everything to us. "
            f"Explore our latest fragrances — we think you'll love them!\n\n"
            f"Tuxwood Perfumes ✨\n\n"
            f"---\n"
            f"مرحباً {display_name}! 🌿\n"
            f"أهلاً بعودتك! وجودك معنا يسعدنا دائماً. شكراً لولائك العزيز. ✨"
        )
    elif segment == "VIP":
        return (
            f"Hi {display_name}! 🌿\n\n"
            f"Thank you for being one of Tuxwood's most loyal VIP customers. "
            f"Your trust and support means the world to us! 💎\n\n"
            f"We always strive to bring you the finest fragrances. "
            f"Stay tuned — exciting new arrivals are coming soon!\n\n"
            f"Tuxwood Perfumes ✨\n\n"
            f"---\n"
            f"مرحباً {display_name}! 🌿\n"
            f"شكراً جزيلاً لكونك أحد عملائنا VIP المميزين. ولاؤك يسعدنا كثيراً! 💎"
        )
    elif segment == "Active/Regular":
        return (
            f"Hi {display_name}! 🌿\n\n"
            f"Thank you for always choosing Tuxwood! Your continued support keeps us going. 🌸\n\n"
            f"We appreciate every order you place with us. "
            f"As always, we're here for you — anytime you need your next fragrance!\n\n"
            f"Tuxwood Perfumes ✨\n\n"
            f"---\n"
            f"مرحباً {display_name}! 🌿\n"
            f"شكراً لاختيارك تكسوود دائماً! دعمك المستمر يشجعنا. نحن هنا دائماً لخدمتك. ✨"
        )
    elif segment == "Reactive":
        return (
            f"Hi {display_name}! 🌿\n\n"
            f"It's great to have you back with Tuxwood! 🌸\n\n"
            f"We hope your fragrance has been bringing you joy. "
            f"Whenever you're ready for your next scent, we're just a message away!\n\n"
            f"Tuxwood Perfumes ✨\n\n"
            f"---\n"
            f"مرحباً {display_name}! 🌿\n"
            f"يسعدنا عودتك إلى تكسوود! نأمل أن عطرك يجلب لك البهجة دائماً. ✨"
        )
    else:
        return (
            f"Hi {display_name}! 🌿\n\n"
            f"We miss you at Tuxwood! It's been a while since your last visit. 🌸\n\n"
            f"We have beautiful new fragrances that we think you'll love. "
            f"Come back and explore — we'd love to welcome you again!\n\n"
            f"Tuxwood Perfumes ✨\n\n"
            f"---\n"
            f"مرحباً {display_name}! 🌿\n"
            f"لقد افتقدناك في تكسوود! لدينا عطور جديدة رائعة تنتظرك. ✨"
        )


def submit_for_approval(pending):
    try:
        r = requests.post(
            f"{OZANI_URL}/aslam/preview",
            json={"pending": pending},
            timeout=15
        )
        if r.status_code == 200:
            print(f"✅ Sent {len(pending)} messages to Ozani for approval")
        else:
            print(f"❌ Ozani approval failed: {r.status_code}")
    except Exception as e:
        print(f"❌ Could not reach Ozani: {e}")


def send_whatsapp(message):
    url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"
    r = requests.post(url,
        headers={"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"},
        json={"messaging_product": "whatsapp", "to": OWNER_NUMBER, "type": "text", "text": {"body": message}})
    return r.status_code


def main():
    today   = datetime.now().strftime("%Y-%m-%d")
    weekday = datetime.now().strftime("%A")

    print("=" * 60)
    print("  TUXWOOD — Aslam (Retention Agent) — CLOUD")
    print(f"  Date: {today} | Day: {weekday}")
    print("=" * 60)

    if not GOOGLE_CREDENTIALS:
        print("❌ GOOGLE_CREDENTIALS not set.")
        send_whatsapp("❌ Aslam: GOOGLE_CREDENTIALS not configured in Railway.")
        return

    sheet = connect_google_sheet()
    if not sheet:
        send_whatsapp("❌ Aslam: Could not connect to Google Sheets. Check credentials.")
        return

    contacts = fetch_contacts(sheet)
    if not contacts:
        send_whatsapp("❌ Aslam: No contacts found in Google Sheet.")
        return

    log = load_log()
    week_key = datetime.now().strftime("%Y-W%W")

    pending = []
    segment_counts = {}

    for contact in contacts:
        name    = str(contact.get("Customer Name", "")).strip()
        phone   = str(contact.get("Mobile Number", "")).strip()
        country = str(contact.get("Country", "")).strip()
        segment = str(contact.get("Customer Segment", "")).strip()

        if country not in TARGET_COUNTRIES:
            continue
        if segment not in TARGET_SEGMENTS:
            continue

        contact_key = f"{phone}_{week_key}"
        if contact_key in log:
            continue

        seg_count = segment_counts.get(segment, 0)
        if seg_count >= MAX_PER_SEGMENT:
            continue

        msg = generate_message(name, segment)
        pending.append({
            "type":    "retention",
            "name":    name,
            "phone":   phone,
            "segment": segment,
            "date":    today,
            "key":     contact_key,
            "message": msg
        })
        segment_counts[segment] = seg_count + 1

    if not pending:
        print("✅ No pending retention messages this week.")
        send_whatsapp(
            f"📱 *Aslam — Weekly Retention*\n"
            f"📅 {today}\n\n"
            f"✅ All customers already contacted this week.\n"
            f"🤖 Aslam — Retention Agent"
        )
        return

    print(f"\n📊 Retention breakdown:")
    for seg, count in segment_counts.items():
        print(f"  {seg}: {count}")
    print(f"  Total: {len(pending)}")

    print(f"\n📤 Sending to Ozani for owner approval...")
    submit_for_approval(pending)

    for item in pending:
        log[item["key"]] = {
            "name":    item["name"],
            "phone":   item["phone"],
            "segment": item["segment"],
            "week":    week_key,
            "date":    today
        }
    save_log(log)
    print("✅ Done. Owner will receive WhatsApp approval request.")


if __name__ == "__main__":
    main()
