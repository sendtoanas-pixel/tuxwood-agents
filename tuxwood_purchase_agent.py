"""
TUXWOOD — Shahan (Post-Purchase Follow-up Agent) — CLOUD VERSION
=================================================================
Runs every 15 minutes. Checks Gmail for NEW (unread) sales report emails.
Processes immediately when a new report arrives — no fixed schedule needed.

Synced 2026-07-18 from the local AGENT AI copy (last updated 2026-07-16),
which had drifted 2+ months ahead of this Railway deploy folder. This sync
brings in: owner-forwarding (forward_to_owner), per-message-type photo
attachments, Day 3 cross-sell, Loyalty offer (day 25) / Check-in (day 15),
VIP handling, the resolve_day1_key repeat-purchase dedup fix (2026-07-16),
the multi-day superseded-report catch-up scan, and corrupted-log
auto-repair. See project memory for full history of these fixes.

DAY 1 -> Thank you message  (sent as soon as sales report is found)
DAY 3 -> Google Review request + cross-sell (checked on every run)
DAY 15 -> Check-in
DAY 25 -> Loyalty offer (or VIP message for 3+ time customers)

Deploy on Railway as a CRON job:
  Schedule: */15 * * * *  (every 15 minutes, all day)
  Command:  python tuxwood_purchase_agent.py --auto
"""

import pandas as pd
import requests
import json
import os
import re
import sys
import shutil
from datetime import datetime, timedelta

os.environ.setdefault("GMAIL_APP_PASSWORD", "paijshbwffiokrqn")
os.environ.setdefault("GMAIL_USER", "sendtoanas@gmail.com")

from gmail_helper import fetch_new_report_from_gmail, read_sales_report as _read_file

# ============================================================
# CONFIG
# ============================================================
WHATSAPP_TOKEN     = os.environ.get("WHATSAPP_TOKEN", "EAAXY3FLEH2kBR3gVNvmGhIsLfxOUzh56RVsZCBeEr6lAk7i4sfYaqlsZATZCDUCf9ZCJhb68RcD1aZAHfYZBQULxJ3DlPE7Ut7CaxFZBidRBDQXzI2dhFBZCWxmnVw6SopV1ooDHZCnckRcR40YJaifbZCFBNEyceSCdrvTHZAzCKWiqZAFIeldcvhZAZBZAYsdM5cHSgZDZD")
PHONE_NUMBER_ID    = os.environ.get("PHONE_NUMBER_ID", "1127995510386994")
GOOGLE_REVIEW_LINK = "https://g.page/r/CWD2JXuNUfFNEAE/review"
OWNER_FORWARD_PHONE = "971569394846"  # Anas's personal number -- added 2026-07-09
                                       # so every customer message Shahan sends
                                       # (thank you, review request, loyalty
                                       # offer, check-in, cross-sell, VIP) gets
                                       # forwarded here too, for visibility.
# Persistent data directory — set DATA_DIR to a mounted Railway Volume path
# so the sent-message log survives cron teardown/restarts (same pattern as
# tuxwood_sales_chatbot.py's DATA_DIR). Falls back to the script's own
# directory when running locally / no volume is attached.
DATA_DIR = os.environ.get("DATA_DIR", os.path.dirname(os.path.abspath(__file__)))
os.makedirs(DATA_DIR, exist_ok=True)
LOG_FILE           = os.path.join(DATA_DIR, "tuxwood_purchase_log.json")

# One-time seed: if this is a brand-new volume with no log yet, copy in the
# real dedup history (tuxwood_purchase_log.seed.json, committed alongside
# this script) instead of starting blank -- starting blank would make the
# script think NO customer has ever been messaged and re-send thank-you /
# review-request texts to everyone in the sales history on the first run.
if not os.path.exists(LOG_FILE):
    _seed_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tuxwood_purchase_log.seed.json")
    if os.path.exists(_seed_path):
        shutil.copy(_seed_path, LOG_FILE)
        print(f"Seeded {LOG_FILE} from {_seed_path}")
STORE_PHOTO_URL    = "https://tuxwood-cloud-production.up.railway.app/store-photo"  # generic fallback photo

# Per-message-type photos -- added 2026-07-14 (Anas provided these). Each
# message type sends its own dedicated photo instead of the generic store
# photo above. Files live next to this script; uploaded once to WhatsApp's
# Media API and cached as a media ID (see get_photo_media_id below) so we
# don't re-upload the same image on every run.
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MTYPE_PHOTO_FILES = {
    "day1_thankyou": os.path.join(SCRIPT_DIR, "thankyou_photo.jpg"),
    "day3_review":   os.path.join(SCRIPT_DIR, "review_photo.jpg"),
    "day7_loyalty":  os.path.join(SCRIPT_DIR, "loyalty_checkin_photo.jpg"),
    "day14_checkin": os.path.join(SCRIPT_DIR, "loyalty_checkin_photo.jpg"),
}
MEDIA_ID_CACHE_FILE = os.path.join(SCRIPT_DIR, "photo_media_ids.json")


def _load_media_id_cache():
    if os.path.exists(MEDIA_ID_CACHE_FILE):
        try:
            with open(MEDIA_ID_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def _save_media_id_cache(cache):
    try:
        tmp_path = MEDIA_ID_CACHE_FILE + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, MEDIA_ID_CACHE_FILE)
    except Exception as e:
        print("  ⚠️  Could not save photo media ID cache: {}".format(e))


def upload_whatsapp_media(file_path):
    """Upload a local image to WhatsApp's Media API once and return its
    media ID. Using an ID (instead of a public link) means these photos
    never need a Railway route or redeploy -- everything stays local to
    this script."""
    url = "https://graph.facebook.com/v18.0/{}/media".format(PHONE_NUMBER_ID)
    headers = {"Authorization": "Bearer {}".format(WHATSAPP_TOKEN)}
    with open(file_path, "rb") as f:
        files = {"file": (os.path.basename(file_path), f, "image/jpeg")}
        data = {"messaging_product": "whatsapp", "type": "image/jpeg"}
        r = requests.post(url, headers=headers, files=files, data=data)
    if r.status_code != 200:
        print("  ❌ Photo upload FAILED for {} — status {}: {}".format(file_path, r.status_code, r.text[:500]))
        return None
    return r.json().get("id")


def get_photo_media_id(mtype):
    """Return a cached WhatsApp media ID for this message type's photo,
    uploading it the first time it's needed. Returns None if there's no
    dedicated photo for this type or the upload fails -- callers should
    fall back to STORE_PHOTO_URL in that case."""
    file_path = MTYPE_PHOTO_FILES.get(mtype)
    if not file_path or not os.path.exists(file_path):
        return None
    cache = _load_media_id_cache()
    cache_key = os.path.basename(file_path)
    if cache_key in cache:
        return cache[cache_key]
    media_id = upload_whatsapp_media(file_path)
    if media_id:
        cache[cache_key] = media_id
        _save_media_id_cache(cache)
    return media_id


def _find_downloads_dir():
    if os.name == "nt":
        return os.path.join(os.path.expanduser("~"), "Downloads")
    import glob
    candidates = glob.glob("/sessions/*/mnt/Downloads")
    return candidates[0] if candidates else os.path.join(os.path.expanduser("~"), "Downloads")
DOWNLOADS_DIR = _find_downloads_dir()
# ============================================================


def _auto_repair_truncated_json(path, is_list_under_key=None):
    """
    If a JSON file was cut off mid-write (e.g. process killed during save),
    salvage everything up to the last complete record instead of losing the
    whole file. Backs up the corrupt copy first. Returns the recovered dict,
    or None if it couldn't be salvaged.
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
        marker = '\n    },\n' if is_list_under_key else '\n  },\n'
        idx = text.rfind(marker)
        if idx == -1:
            return None
        if is_list_under_key:
            truncated = text[:idx] + '\n    }\n  ]\n}'
        else:
            truncated = text[:idx] + '\n  }\n}'
        data = json.loads(truncated)  # validate before trusting it
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        shutil.copy(path, f"{path}.corrupt_backup_{ts}")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"⚠️  {os.path.basename(path)} was truncated (interrupted write) — "
              f"auto-repaired, corrupt copy saved as {os.path.basename(path)}.corrupt_backup_{ts}")
        return data
    except Exception as e:
        print(f"❌ Could not auto-repair {os.path.basename(path)}: {e}")
        return None


def load_log():
    if not os.path.exists(LOG_FILE):
        return {}
    try:
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        print(f"❌ {os.path.basename(LOG_FILE)} is corrupted ({e}) — attempting auto-repair...")
        repaired = _auto_repair_truncated_json(LOG_FILE, is_list_under_key=False)
        if repaired is not None:
            return repaired
        # Last resort: don't crash the whole run over a bad log file. Back up
        # the unreadable file and start fresh rather than silently losing the
        # ability to run at all (this previously caused Shahan to fail every
        # 30-minute run for 2+ days without anyone noticing).
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        try:
            shutil.copy(LOG_FILE, f"{LOG_FILE}.unreadable_{ts}")
        except Exception:
            pass
        print("⚠️  Starting with an empty follow-up log — corrupt file preserved for inspection. "
              "Some customers may receive a duplicate thank-you message.")
        return {}


def save_log(log):
    """Atomic write: write to a temp file then rename, so a crash/kill mid-save
    can never leave tuxwood_purchase_log.json truncated/corrupted again."""
    tmp_path = LOG_FILE + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, LOG_FILE)


def format_phone(raw_phone):
    phone = str(raw_phone).strip()
    if "e" in phone.lower() or "." in phone:
        try:
            phone = str(int(float(phone)))
        except Exception:
            return None
    phone = phone.replace("+", "").replace("-", "").replace(" ", "")
    if not phone or phone == "nan":
        return None
    if not phone.startswith("971") and len(phone) == 9:
        phone = "971" + phone
    return phone


def read_sales_report(file_path):
    df = _read_file(file_path)
    df = df.dropna(subset=["Customer Name"])
    if "Invoice Date" in df.columns:
        df = df.dropna(subset=["Invoice Date"])
    if "Mobile Number" in df.columns:
        df["Mobile Number"] = df["Mobile Number"].apply(format_phone)
        df = df[df["Mobile Number"].notna()]
    return df


def find_report_in_downloads():
    # Resolve the downloads dir at runtime (handles session path changes)
    global DOWNLOADS_DIR
    import glob as _glob
    if os.name == "nt":
        dl_dir = os.path.join(os.path.expanduser("~"), "Downloads")
    else:
        _cands = _glob.glob("/sessions/*/mnt/Downloads")
        dl_dir = _cands[0] if _cands else DOWNLOADS_DIR
    if not os.path.isdir(dl_dir):
        return None
    DOWNLOADS_DIR = dl_dir
    keywords = ["sales", "order", "report", "tuxwood", "invoice"]
    candidates = []
    for fname in os.listdir(DOWNLOADS_DIR):
        if not fname.lower().endswith((".xlsx", ".xls")):
            continue
        if any(kw in fname.lower() for kw in keywords):
            full_path = os.path.join(DOWNLOADS_DIR, fname)
            candidates.append((os.path.getmtime(full_path), full_path, fname))
    if not candidates:
        return None
    candidates.sort(reverse=True)
    mtime, path, fname = candidates[0]
    modified_str = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
    print("Found in Downloads: {} (modified {})".format(fname, modified_str))
    return path


def _report_date_span(fname):
    """Pull (start, end, span_days) out of a filename like
    'Sales Summary Report 3_2026-07-06_2026-07-07.xlsx'. Returns None if the
    filename doesn't contain a recognizable YYYY-MM-DD_YYYY-MM-DD date range."""
    import re
    m = re.search(r"(\d{4}-\d{2}-\d{2})_(\d{4}-\d{2}-\d{2})", fname)
    if not m:
        return None
    try:
        start = datetime.strptime(m.group(1), "%Y-%m-%d")
        end = datetime.strptime(m.group(2), "%Y-%m-%d")
        return start, end, (end - start).days
    except Exception:
        return None


def find_reports_in_downloads(days_back=14, max_span_days=3):
    """Return ALL matching *daily* report files from the last `days_back` days
    (oldest first).

    Fix (2026-07-08): the old find_report_in_downloads() only ever looked at the
    single most-recently-modified file. If a WhatsApp send failed (sandbox/network
    block) or a run was simply missed, and a NEWER report then landed before the
    older one's customers were ever sent, those customers were silently skipped
    forever -- the script never looked back at superseded files. This scans a
    rolling window instead so nobody already-unsent gets permanently dropped.

    Safety filter (also added 2026-07-08, found while testing the fix above):
    Anas periodically re-downloads large CUMULATIVE reports (e.g. a full
    2025-07-01_2026-06-30 export, 1500+ rows) into the same Downloads folder.
    A pure mtime-based window would treat those as "new reports" too and queue
    a Day-1 "welcome" message to hundreds of customers who bought months ago.
    So candidates are also required to have a narrow date range IN THE FILENAME
    (<= max_span_days) -- this is what distinguishes the real daily export from
    a historical dump. Files without a parseable two-date filename pattern are
    skipped entirely rather than guessed at.
    """
    global DOWNLOADS_DIR
    import glob as _glob
    if os.name == "nt":
        dl_dir = os.path.join(os.path.expanduser("~"), "Downloads")
    else:
        _cands = _glob.glob("/sessions/*/mnt/Downloads")
        dl_dir = _cands[0] if _cands else DOWNLOADS_DIR
    if not os.path.isdir(dl_dir):
        return []
    DOWNLOADS_DIR = dl_dir
    keywords = ["sales", "order", "report", "tuxwood", "invoice"]
    cutoff = datetime.now().timestamp() - days_back * 86400
    candidates = []
    for fname in os.listdir(DOWNLOADS_DIR):
        if not fname.lower().endswith((".xlsx", ".xls")):
            continue
        if not any(kw in fname.lower() for kw in keywords):
            continue
        span_info = _report_date_span(fname)
        if span_info is None:
            continue  # can't confirm it's a daily report -- skip for safety
        _start, _end, span = span_info
        if span > max_span_days:
            continue  # looks like a historical/cumulative export, not a daily one
        full_path = os.path.join(DOWNLOADS_DIR, fname)
        mtime = os.path.getmtime(full_path)
        if mtime >= cutoff:
            candidates.append((mtime, full_path, fname))
    candidates.sort()  # oldest first
    return candidates


def send_whatsapp(phone, message):
    url = "https://graph.facebook.com/v18.0/{}/messages".format(PHONE_NUMBER_ID)
    headers = {
        "Authorization": "Bearer {}".format(WHATSAPP_TOKEN),
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": phone,
        "type": "text",
        "text": {"body": message}
    }
    r = requests.post(url, headers=headers, json=payload)
    return r.status_code, r.json()


MTYPE_LABELS = {
    "day1_thankyou": "Day 1 Thank You",
    "day3_review": "Day 3 Review Request",
    "day3_crosssell": "Day 3 Cross-Sell",
    "day7_loyalty": "Loyalty Offer",
    "day14_checkin": "Check-In",
    "vip": "VIP Offer",
}

# ── Owner-forward template (added 2026-07-14) ──────────────────────────────
# Plain WhatsApp sends (text or image) can only reach a number that has
# messaged the business number within the last 24h (Meta's customer-service
# window). Anas doesn't regularly text Shahan's bot number, so forwards to
# OWNER_FORWARD_PHONE were likely being silently rejected every time that
# window was closed -- this is the same root cause fixed for Ozani's chat
# forwarding on 2026-07-13 (see memory: project_tuxwood_ozani_owner_forwarding_fix).
# A pre-approved WhatsApp TEMPLATE bypasses the window entirely. Run
# CREATE_SHAHAN_TEMPLATE.bat once (locally -- this sandbox has no route to
# Meta's API) to submit "shahan_owner_forward" for approval. Until Meta
# approves it, forward_to_owner() below falls back to the old freeform
# image send automatically -- nothing breaks in the meantime.
WABA_ID                     = "2176442326500478"
OWNER_FORWARD_TEMPLATE      = "shahan_owner_forward"
OWNER_FORWARD_TEMPLATE_LANG = "en_US"


def _sanitize_template_param(text, max_len=1024):
    """WhatsApp template parameters reject newlines/tabs, 4+ consecutive
    spaces, and empty strings. Clean freeform text before dropping it into
    a template so the send doesn't fail on formatting."""
    text = (text or "").replace("\n", " / ").replace("\t", " ")
    text = re.sub(r"\s{2,}", " ", text).strip()
    if not text:
        return "(none)"
    if len(text) > max_len:
        text = text[:max_len].rstrip() + "…"
    return text


def send_whatsapp_template(to, template_name, lang_code, body_params, header_image_id=None):
    """Send a pre-approved WhatsApp template message. Unlike send_whatsapp(),
    template messages bypass Meta's 24-hour customer-service window,
    reaching numbers (like the owner's) that haven't recently texted the
    bot number. `body_params` is an ordered list of strings filling {{1}},
    {{2}}, ... in the template body. Returns True on success, False
    otherwise (e.g. the template isn't approved yet)."""
    url = "https://graph.facebook.com/v18.0/{}/messages".format(PHONE_NUMBER_ID)
    headers = {"Authorization": "Bearer {}".format(WHATSAPP_TOKEN), "Content-Type": "application/json"}
    components = []
    if header_image_id:
        components.append({
            "type": "header",
            "parameters": [{"type": "image", "image": {"id": header_image_id}}]
        })
    components.append({
        "type": "body",
        "parameters": [{"type": "text", "text": p} for p in body_params]
    })
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "template",
        "template": {
            "name": template_name,
            "language": {"code": lang_code},
            "components": components
        }
    }
    r = requests.post(url, headers=headers, json=payload)
    if r.status_code != 200:
        print("  ❌ WhatsApp TEMPLATE send FAILED to {} ({}) — status {}: {}".format(to, template_name, r.status_code, r.text[:500]))
        return False
    return True


def forward_to_owner(mtype, name, phone, msg):
    """Forward a copy of every customer-facing message to Anas's personal
    WhatsApp (added 2026-07-09) so he can see what Shahan is sending without
    checking the log. Best-effort -- a forwarding failure must never block or
    fail the actual customer send.

    Updated 2026-07-22: switched from the WhatsApp TEMPLATE approach to a
    plain freeform text message. The template ("shahan_owner_forward") was
    never approved by Meta -- every single attempt failed with a 404
    "template does not exist" error, so owner forwards were silently
    dropped. Plain text is simpler and avoids the photo-upload step, but
    note it still carries WhatsApp's normal 24-hour customer-service-window
    rule: OWNER_FORWARD_PHONE must have messaged the Shahan bot number
    within the last 24h for a freeform message to deliver. If forwards stop
    arriving again, that's most likely the window closing (send the bot
    number any WhatsApp message to reopen it), not a code bug. The only way
    to fully bypass the window is getting a template approved by Meta."""
    label = MTYPE_LABELS.get(mtype, mtype)
    caption = "📤 Shahan sent *{}* to {} ({}):\n\n{}".format(label, name, phone, msg)

    try:
        url = "https://graph.facebook.com/v18.0/{}/messages".format(PHONE_NUMBER_ID)
        headers = {"Authorization": "Bearer {}".format(WHATSAPP_TOKEN), "Content-Type": "application/json"}
        payload = {
            "messaging_product": "whatsapp",
            "to": OWNER_FORWARD_PHONE,
            "type": "text",
            "text": {"body": caption}
        }
        r = requests.post(url, headers=headers, json=payload)
        if r.status_code != 200:
            print("  ⚠️  Owner forward FAILED — status {}: {}".format(r.status_code, r.text[:300]))
    except Exception as e:
        print("  ⚠️  Could not forward copy to owner: {}".format(e))


def generate_thankyou(name, items):
    display_name = name if not name.replace(" ", "").isdigit() else "Valued Customer"
    return (
        "Hi {}! \U0001f33f\n\n"
        "Thanks for choosing Tuxwood. Let's begin your fragrance journey with us ✨"
    ).format(display_name)


def generate_review_request(name):
    display_name = name if not name.replace(" ", "").isdigit() else "Valued Customer"
    return (
        "Hi {},\n\n"
        "We hope you're enjoying your Tuxwood fragrance! \U0001f33f\n"
        "If you loved the experience, we'd be truly grateful if you could share a quick Google review"
        " -- it helps us discover new creations.\n\n"
        "\U0001f449 {}\n\n"
        "Tuxwood Perfumes Team ✨"
    ).format(display_name, GOOGLE_REVIEW_LINK)


def generate_day3_crosssell(name, items):
    """Day 3: after review request, suggest a complementary perfume."""
    display_name = name if not name.replace(" ", "").isdigit() else "Valued Customer"
    items_lower = items.lower() if items else ""
    # Suggest based on what they bought
    if any(x in items_lower for x in ["oud", "sulthan", "ligero", "manly", "force"]):
        suggestion = "Mountain Fresh or Ice — a fresh daytime contrast to your bold scent"
    elif any(x in items_lower for x in ["fresh", "ice", "rainy", "kosovo"]):
        suggestion = "Royal Velvet or Enigma — a warm evening complement"
    elif any(x in items_lower for x in ["royal", "rosy", "holysmells", "queen"]):
        suggestion = "Ockacho or Ember — a luxurious match for your taste"
    else:
        suggestion = "Force (AED 69) or Ockacho (AED 89) — our best sellers this week"
    return (
        "Hi {} 🌿\n\n"
        "Since you loved your Tuxwood fragrance, you might also enjoy:\n\n"
        "👉 {}\n\n"
        "Reply 'YES' and we'll arrange delivery right away!\n\n"
        "Tuxwood Perfumes ✨"
    ).format(display_name, suggestion)


def generate_day7_loyalty(name):
    """Loyalty offer — combo deal. Triggers on day 25 since purchase (changed
    2026-07-09, was day 7 — kept the type/log field name "day7_loyalty" for
    backward compatibility, only the trigger timing changed)."""
    display_name = name if not name.replace(" ", "").isdigit() else "Valued Customer"
    return (
        "Hi {} 🌿\n\n"
        "It's been a month since your Tuxwood order — we hope you're still loving it!\n\n"
        "As a thank-you for being a valued customer, here's a special offer just for you:\n\n"
        "🎁 Buy any 2 perfumes and get FREE delivery + a 10 ML Sample Bottle on your next order!\n\n"
        "Just reply 'DEAL' and we'll take care of everything 😊\n\n"
        "Tuxwood Perfumes ✨"
    ).format(display_name)


def generate_day14_checkin(name):
    """Day 14: friendly check-in to build relationship."""
    display_name = name if not name.replace(" ", "").isdigit() else "Valued Customer"
    return (
        "Hi {} 🌿\n\n"
        "Just checking in — how are you enjoying your Tuxwood fragrance? "
        "We'd love to know your favourite moment wearing it!\n\n"
        "And if you're ready to explore a new scent, we have exciting new arrivals 🌸\n\n"
        "Tuxwood Perfumes ✨"
    ).format(display_name)


def generate_vip_message(name, purchase_count):
    """Special message for VIP customers (3+ purchases)."""
    display_name = name if not name.replace(" ", "").isdigit() else "Valued Customer"
    return (
        "Hi {} 👑\n\n"
        "You're one of our most valued Tuxwood customers — {} orders and counting!\n\n"
        "As a VIP, you get first access to our new collection before anyone else.\n\n"
        "Reply 'VIP' and we'll share exclusive previews with you 🌿✨\n\n"
        "Tuxwood Perfumes"
    ).format(display_name, purchase_count)


def get_purchase_count(log, phone):
    """Count how many times this phone number has purchased."""
    return sum(1 for k, v in log.items()
               if isinstance(v, dict) and v.get("phone") == phone and v.get("day1_sent"))


def resolve_day1_key(log, phone, purchase_date):
    """Given a phone number and THIS purchase's date, figure out whether a
    Day 1 message has already gone out for this specific purchase, and if
    not, what log key to file it under.

    Fixed 2026-07-16 (Anas's request): dedup used to be phone-only ("if this
    phone has ever gotten a Day 1, skip"). That meant a repeat customer's
    second, third, etc. purchase was silently dropped forever -- never
    logged, never messaged, no trace it happened -- because the phone
    already had a day1_sent flag from an earlier purchase. Caught via ANAS's
    own test number (0569394846): a new 07-15 purchase never queued because
    a 05-30 purchase was already marked sent.

    Now a phone that already exists in the log gets a new entry keyed
    "<phone>_<purchase_date>" whenever the purchase date doesn't match what's
    already on record, instead of being treated as a duplicate. The original
    phone-only key is still used for a customer's first-ever purchase, so
    nothing about existing history/keys changes.

    Returns (already_sent: bool, key: str).
    """
    existing_key = None
    if phone in log and log[phone].get("purchase_date") == purchase_date:
        existing_key = phone
    else:
        for k, v in log.items():
            if isinstance(v, dict) and v.get("phone") == phone and v.get("purchase_date") == purchase_date:
                existing_key = k
                break

    if existing_key:
        return bool(log[existing_key].get("day1_sent")), existing_key

    # No log entry for this exact purchase yet.
    if phone not in log:
        return False, phone
    return False, "{}_{}".format(phone, purchase_date)


def load_from_downloads(log, today, pending):
    reports = find_reports_in_downloads()
    if not reports:
        print("No sales report found in Downloads.")
        print("  -> Export the report from Dot Orders and save it to your Downloads folder.")
        return False

    seen_keys = set()   # dedupe across multiple overlapping report files in this same run
    total_queued  = 0
    total_skipped = 0
    latest_fname  = None
    any_ok = False

    for mtime, fallback_file, fname in reports:
        try:
            df = read_sales_report(fallback_file)
        except Exception as e:
            print("Error reading {}: {}".format(fname, e))
            continue

        any_ok = True
        queued  = 0
        skipped = 0
        for _, row in df.iterrows():
            name  = str(row.get("Customer Name", "Valued Customer")).strip()
            phone = str(row.get("Mobile Number", "")).strip()
            items = str(row.get("Items", "your fragrance")).strip()
            date  = ""
            if "Invoice Date" in df.columns:
                raw_date = row.get("Invoice Date", "")
                try:
                    date = pd.to_datetime(raw_date, errors="coerce").strftime("%Y-%m-%d")
                except Exception:
                    date = today

            # Dedup key: phone + purchase date (fixed 2026-07-16, see
            # resolve_day1_key). seen_keys here only catches the same
            # customer's same purchase appearing twice across overlapping
            # report files in this one run -- a genuinely new purchase date
            # for an existing phone is never treated as a duplicate.
            purchase_date = date or today
            dedupe_key = (phone, purchase_date)
            if dedupe_key in seen_keys:
                skipped += 1
                continue
            seen_keys.add(dedupe_key)

            already_sent, key = resolve_day1_key(log, phone, purchase_date)
            if already_sent:
                skipped += 1
                continue

            pending.append({
                "type": "day1_thankyou",
                "name": name, "phone": phone,
                "items": items, "date": purchase_date, "key": key
            })
            queued += 1

        modified_str = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
        print("{} rows from {} (modified {}) -> queued {}, skipped {}".format(
            len(df), fname, modified_str, queued, skipped))
        total_queued  += queued
        total_skipped += skipped
        latest_fname = fname

    if not any_ok:
        return False

    if latest_fname:
        log["last_processed_file"] = latest_fname
    print("Queued: {} | Already sent (skipped): {}".format(total_queued, total_skipped))
    return True


def run_purchase_agent():
    today   = datetime.now().strftime("%Y-%m-%d")
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

    print("=" * 60)
    print("  TUXWOOD -- Shahan (Post-Purchase Agent) -- CLOUD")
    print("  {}".format(now_str))
    print("=" * 60)

    log = load_log()
    pending = []

    # STEP 1: Get today's sales report
    print("\nChecking Gmail for new sales report...")
    result = fetch_new_report_from_gmail(unread_only=True)

    if result:
        report_file, email_uid = result
        if log.get("last_processed_email_uid") == email_uid:
            print("Email UID {} already processed -- skipping Day 1 check.".format(email_uid))
        else:
            print("New report from Gmail (UID: {})".format(email_uid))
            try:
                df = read_sales_report(report_file)
                print("{} total rows loaded from Gmail report".format(len(df)))
                skipped = 0
                queued  = 0
                for _, row in df.iterrows():
                    name  = str(row.get("Customer Name", "Valued Customer")).strip()
                    phone = str(row.get("Mobile Number", "")).strip()
                    items = str(row.get("Items", "your fragrance")).strip()
                    date  = ""
                    if "Invoice Date" in df.columns:
                        try:
                            date = pd.to_datetime(row.get("Invoice Date", ""), errors="coerce").strftime("%Y-%m-%d")
                        except Exception:
                            date = today
                    purchase_date = date or today
                    already_sent, key = resolve_day1_key(log, phone, purchase_date)
                    if already_sent:
                        skipped += 1
                        continue
                    pending.append({
                        "type": "day1_thankyou",
                        "name": name, "phone": phone,
                        "items": items, "date": purchase_date, "key": key
                    })
                    queued += 1
                print("Queued: {} | Already sent (skipped): {}".format(queued, skipped))
                log["last_processed_email_uid"] = email_uid
            except Exception as e:
                print("Error reading Gmail report: {}".format(e))
    else:
        print("Gmail not available -- trying Downloads folder...")
        load_from_downloads(log, today, pending)

    # STEP 2: Day 3 Google Review + Cross-sell / Loyalty offer / Check-in / VIP
    #
    # Fix (2026-07-09): these used to require an EXACT date match
    # (purchase_date == today - N days). If Day 1 was ever sent late (e.g. the
    # superseded-report backlog fixed 2026-07-08), a customer's follow-up date
    # had often already passed by the time they were first logged -- and since
    # the check only ever looked at that single exact day, they'd be silently
    # skipped forever. Same failure mode as the original Day 1 bug, just at a
    # later stage. Now uses "days since purchase >= N" instead of "==", with a
    # 14-day catch-up grace window, so a late Day 1 send doesn't permanently
    # forfeit the later stages. Once a stage's *_sent flag is set it won't
    # refire, so this doesn't double-send anyone already caught by the old
    # exact-match logic while it was working.
    #
    # Retimed 2026-07-09 (Anas's request): loyalty offer now fires on day 25
    # since purchase (was day 7), check-in now fires on day 15 (was day 14).
    # Both now auto-send with no approval needed (previously required
    # approval) -- see auto_types below. Kept the "day7_loyalty"/"day14_checkin"
    # type strings and "day7_sent"/"day14_sent" log field names as-is even
    # though the actual trigger days changed, to avoid touching every place
    # that reads those field names -- only the timing and approval requirement
    # changed, not the internal labels.
    now_dt = datetime.now()
    CATCHUP_WINDOW_DAYS = 14
    LOYALTY_OFFER_DAY = 25
    CHECKIN_DAY = 15

    def _days_since_purchase(purchase_date_str):
        try:
            purch_dt = datetime.strptime(purchase_date_str, "%Y-%m-%d")
        except Exception:
            return None
        return (now_dt.date() - purch_dt.date()).days

    for phone_key, entry in log.items():
        if not isinstance(entry, dict):
            continue
        purchase_date = entry.get("purchase_date", "")
        phone = entry.get("phone", "")
        name  = entry.get("name", "Valued Customer")
        items = entry.get("items", "")
        days_since = _days_since_purchase(purchase_date)
        if days_since is None:
            continue

        # Day 3 — Google review (window: 2-16 days since purchase)
        if 2 <= days_since <= 2 + CATCHUP_WINDOW_DAYS and not entry.get("day3_sent"):
            pending.append({
                "type": "day3_review",
                "name": name, "phone": phone,
                "items": items, "date": purchase_date, "key": phone_key
            })
            # Also queue cross-sell right after review
            pending.append({
                "type": "day3_crosssell",
                "name": name, "phone": phone,
                "items": items, "date": purchase_date, "key": phone_key
            })

        # Loyalty offer — day 25 since purchase (window: 25-39 days)
        if LOYALTY_OFFER_DAY <= days_since <= LOYALTY_OFFER_DAY + CATCHUP_WINDOW_DAYS and not entry.get("day7_sent"):
            purchase_count = get_purchase_count(log, phone)
            if purchase_count >= 3:
                # VIP customer
                pending.append({
                    "type": "vip",
                    "name": name, "phone": phone, "count": purchase_count,
                    "items": items, "date": purchase_date, "key": phone_key
                })
            else:
                pending.append({
                    "type": "day7_loyalty",
                    "name": name, "phone": phone,
                    "items": items, "date": purchase_date, "key": phone_key
                })

        # Check-in — day 15 since purchase (window: 15-29 days)
        if CHECKIN_DAY <= days_since <= CHECKIN_DAY + CATCHUP_WINDOW_DAYS and not entry.get("day14_sent"):
            pending.append({
                "type": "day14_checkin",
                "name": name, "phone": phone,
                "items": items, "date": purchase_date, "key": phone_key
            })

    # STEP 3: Build messages and save for approval
    if not pending:
        print("\nNo pending messages — all done for today.")
        save_log(log)
        return

    OWNER_PHONE     = "971528903429"
    PENDING_FILE    = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pending_messages.json")

    # Generate message text for each item
    for item in pending:
        name  = item["name"]
        mtype = item["type"]
        if mtype == "day1_thankyou":
            item["msg"] = generate_thankyou(name, item["items"])
        elif mtype == "day3_review":
            item["msg"] = generate_review_request(name)
        elif mtype == "day3_crosssell":
            item["msg"] = generate_day3_crosssell(name, item.get("items", ""))
        elif mtype == "day7_loyalty":
            item["msg"] = generate_day7_loyalty(name)
        elif mtype == "day14_checkin":
            item["msg"] = generate_day14_checkin(name)
        elif mtype == "vip":
            item["msg"] = generate_vip_message(name, item.get("count", 3))
        else:
            item["msg"] = generate_review_request(name)

    # --auto mode: send directly, no approval needed
    # Updated 2026-07-09 (Anas's request): loyalty offer (day 25) and check-in
    # (day 15) now auto-send too, same as Day 1 thank-you and Day 3 review.
    # Cross-sell and VIP still require approval.
    auto_mode = "--auto" in sys.argv
    if auto_mode:
        auto_types = {"day1_thankyou", "day3_review", "day7_loyalty", "day14_checkin"}
        auto_send  = [m for m in pending if m["type"] in auto_types]
        needs_approval = [m for m in pending if m["type"] not in auto_types]

        if auto_send:
            print("\n🤖 AUTO MODE — Sending Day 1, Day 3, loyalty offer & check-in messages now...")
            sent = 0
            failed = 0
            for item in auto_send:
                phone = item["phone"]
                name  = item["name"]
                mtype = item["type"]
                key   = item["key"]
                msg   = item.get("msg", "")
                try:
                    url = "https://graph.facebook.com/v18.0/{}/messages".format(PHONE_NUMBER_ID)
                    headers = {"Authorization": "Bearer {}".format(WHATSAPP_TOKEN), "Content-Type": "application/json"}
                    # Use this message type's dedicated photo (uploaded once,
                    # cached as a media ID) if we have one; otherwise fall
                    # back to the generic store photo link. Added 2026-07-14.
                    media_id = get_photo_media_id(mtype)
                    image_param = {"id": media_id} if media_id else {"link": STORE_PHOTO_URL}
                    image_param["caption"] = msg
                    payload = {
                        "messaging_product": "whatsapp",
                        "to": phone,
                        "type": "image",
                        "image": image_param
                    }
                    r = requests.post(url, headers=headers, json=payload)
                    if r.status_code == 200:
                        print("  ✅ Sent [{}] -> {} ({})".format(mtype, name, phone))
                        sent += 1
                        if key not in log:
                            log[key] = {"name": name, "phone": phone, "items": item.get("items",""), "purchase_date": item["date"]}
                        # Map message type -> the log field the STEP 2 window
                        # checks actually read (entry.get("day7_sent") etc).
                        # Fixed 2026-07-09: a plain string-replace chain here
                        # would have produced "day7_loyalty_sent"/"day14_checkin_sent"
                        # for the newly-auto-sent types, which STEP 2 never
                        # checks (it reads "day7_sent"/"day14_sent") -- so those
                        # two would have re-queued and re-sent on every single
                        # run forever. Explicit mapping avoids that.
                        SENT_FIELD = {
                            "day1_thankyou": "day1",
                            "day3_review": "day3",
                            "day7_loyalty": "day7",
                            "day14_checkin": "day14",
                        }
                        sent_key = SENT_FIELD.get(mtype, mtype)
                        log[key]["{}_sent".format(sent_key)] = True
                        log[key]["{}_sent_at".format(sent_key)] = datetime.now().isoformat()
                        forward_to_owner(mtype, name, phone, msg)
                    else:
                        print("  ❌ Failed [{}] -> {} | {}".format(mtype, name, r.json()))
                        failed += 1
                except Exception as e:
                    print("  ❌ Error sending to {}: {}".format(name, e))
                    failed += 1
            save_log(log)
            print("\n✅ Auto-sent: {} sent, {} failed".format(sent, failed))

        if needs_approval:
            # Merge with any still-unsent items already waiting in PENDING_FILE instead of
            # overwriting them -- otherwise an approved-but-not-yet-sent batch from a previous
            # run gets silently lost when this run generates a fresh list. (Bug found 2026-07-04.)
            existing_pending = []
            if os.path.exists(PENDING_FILE):
                try:
                    with open(PENDING_FILE, "r", encoding="utf-8") as f:
                        existing_pending = json.load(f).get("pending", [])
                except Exception:
                    existing_pending = []
            seen = {(m.get("type"), m.get("key")) for m in needs_approval}
            merged = needs_approval + [m for m in existing_pending if (m.get("type"), m.get("key")) not in seen]
            tmp_path = PENDING_FILE + ".tmp"
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump({"pending": merged, "created_at": datetime.now().isoformat()}, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, PENDING_FILE)
            print("\n⏳ {} message(s) saved for approval (Day 7 / Day 14) -- {} new, {} carried over.".format(
                len(merged), len(needs_approval), len(merged) - len(needs_approval)))
            try:
                lines = ["⏳ *SHAHAN — Approval Needed*\n"]
                for i, m in enumerate(needs_approval, 1):
                    lines.append("{}. {} — {}".format(i, m["name"], m["type"].replace("_"," ").title()))
                lines.append("\nReply in Claude to approve.")
                send_whatsapp(OWNER_PHONE, "\n".join(lines))
            except Exception as e:
                print("⚠️  Could not send preview: {}".format(e))
        return

    # Manual mode: save all for approval
    tmp_path = PENDING_FILE + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump({"pending": pending, "created_at": datetime.now().isoformat()}, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, PENDING_FILE)
    print("\n✅ {} message(s) saved — waiting for your approval.".format(len(pending)))

    preview_lines = ["⏳ *SHAHAN — Approval Required*\n"]
    preview_lines.append("{} message(s) ready to send:".format(len(pending)))
    for i, item in enumerate(pending, 1):
        preview_lines.append("{}. {} ({}) - {}".format(
            i, item["name"], item["phone"], item["type"].replace("_", " ").title()
        ))
    preview_lines.append("\nOpen Claude and say 'send messages' to approve.")
    try:
        send_whatsapp(OWNER_PHONE, "\n".join(preview_lines))
        print("Preview sent to your WhatsApp.")
    except Exception as e:
        print("Could not send WhatsApp preview: {}".format(e))

    print("Waiting for your approval in Claude.")


if __name__ == "__main__":
    run_purchase_agent()
