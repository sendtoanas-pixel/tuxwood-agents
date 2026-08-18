"""
TUXWOOD — One-time backfill: seed the Shahan purchase log from a historical
sales export WITHOUT sending any WhatsApp messages.
=============================================================================
Why this exists (2026-08-18): Muhammed sent a cumulative "Sales Report -
Backfill Jul 1 to Aug 16.xlsx" export to the same Gmail inbox
tuxwood_purchase_agent.py watches. That script's Gmail path has no
protection against cumulative/historical exports (unlike its Downloads-
folder fallback, which skips anything with a >3-day date span in the
filename) -- if this file were picked up by a normal --auto run, STEP 2
would see ~7 weeks of "purchases" all at once and fire a Day 5 Google-review
WhatsApp message to every eligible customer in a single burst (100+
messages, some for orders 6+ weeks old). Muhammed explicitly asked for a
SILENT backfill instead: register these historical purchases in the log
(so dedup and future Day 5 checks behave correctly) without messaging
anyone for them.

WHAT THIS SCRIPT DOES:
  1. Searches Gmail for the exact backfill email by subject
     ("Backfill Jul 1 to Aug 16"), regardless of read/unread status.
  2. Parses its attachment with the exact same read_sales_report/
     format_phone logic tuxwood_purchase_agent.py uses, so entries land in
     the log in a format that script's normal dedup logic already
     understands.
  3. For every row, marks BOTH day1_sent and day3_sent True (with a
     backfilled_2026_08_18 flag for auditability) so neither Day 1 nor Day 5
     will ever fire for these historical purchases. Loyalty/check-in were
     already fully disabled elsewhere, so no equivalent flag needed there.
  4. Writes the updated log via the same atomic save_log() the main script
     uses.
  5. Contains ZERO calls to send_whatsapp / send_whatsapp_template. This
     script cannot message a customer no matter what it finds.

HOW TO RUN (one-time, on Railway):
  Temporarily set this service's start command to:
    python backfill_seed_log.py
  Redeploy, check the logs for the summary line, then set the start command
  back to "python tuxwood_purchase_agent.py --auto" and redeploy again.
"""

import os
import sys
from datetime import datetime

# Reuse the exact same phone/report parsing and log I/O as the live agent,
# rather than reimplementing it and risking a subtle mismatch.
from gmail_helper import read_sales_report as _read_file
import tuxwood_purchase_agent as agent

BACKFILL_SUBJECT_KEYWORD = "Backfill Jul 1 to Aug 16"


def fetch_backfill_attachment():
    """Same IMAP approach as gmail_helper.fetch_new_report_from_gmail, but
    searches by the specific backfill subject and ignores read/unread
    status entirely -- this is a one-time targeted fetch, not part of the
    normal unread-polling loop."""
    import imaplib
    import email
    import tempfile
    from email.header import decode_header

    gmail_user = os.environ.get("GMAIL_USER", "sendtoanas@gmail.com")
    gmail_pass = os.environ.get("GMAIL_APP_PASSWORD", "paijshbwffiokrqn")

    print("Connecting to Gmail to find the backfill report...")
    mail = imaplib.IMAP4_SSL("imap.gmail.com")
    mail.login(gmail_user, gmail_pass)
    mail.select("inbox")

    search_query = '(SUBJECT "{}")'.format(BACKFILL_SUBJECT_KEYWORD)
    _, data = mail.search(None, search_query)
    mail_ids = data[0].split()
    if not mail_ids:
        print("No email found with subject containing '{}'.".format(BACKFILL_SUBJECT_KEYWORD))
        mail.logout()
        return None

    latest_id = mail_ids[-1]
    _, msg_data = mail.fetch(latest_id, "(RFC822)")
    raw_email = msg_data[0][1]
    msg = email.message_from_bytes(raw_email)

    for part in msg.walk():
        if part.get_content_maintype() == "multipart":
            continue
        filename = part.get_filename()
        if not filename or not filename.lower().endswith((".xlsx", ".xls", ".pdf")):
            continue
        decoded = decode_header(filename)
        fname = decoded[0][0]
        if isinstance(fname, bytes):
            fname = fname.decode()
        ext = ".pdf" if filename.lower().endswith(".pdf") else ".xlsx"
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=ext, prefix="backfill_report_")
        tmp.write(part.get_payload(decode=True))
        tmp.close()
        print("Downloaded backfill attachment: {} -> {}".format(fname, tmp.name))
        mail.logout()
        return tmp.name

    print("Email found but no PDF/Excel attachment in it.")
    mail.logout()
    return None


def main():
    print("=" * 60)
    print("  TUXWOOD -- Silent backfill (no messages will be sent)")
    print("  {}".format(datetime.now().strftime("%Y-%m-%d %H:%M")))
    print("=" * 60)

    report_path = fetch_backfill_attachment()
    if not report_path:
        print("Nothing to backfill -- exiting without touching the log.")
        return

    df = agent.read_sales_report(report_path)
    print("{} rows loaded from backfill report".format(len(df)))

    log = agent.load_log()
    today = datetime.now().strftime("%Y-%m-%d")

    new_entries = 0
    already_present = 0
    skipped_bad_row = 0

    for _, row in df.iterrows():
        name = str(row.get("Customer Name", "Valued Customer")).strip()
        phone = str(row.get("Mobile Number", "")).strip()
        items = str(row.get("Items", "your fragrance")).strip()
        if not phone or phone.lower() == "nan":
            skipped_bad_row += 1
            continue

        date = ""
        if "Invoice Date" in df.columns:
            import pandas as pd
            try:
                date = pd.to_datetime(row.get("Invoice Date", ""), errors="coerce").strftime("%Y-%m-%d")
            except Exception:
                date = today
        purchase_date = date or today

        already_sent, key = agent.resolve_day1_key(log, phone, purchase_date)
        if already_sent:
            already_present += 1
            continue

        if key not in log:
            log[key] = {"name": name, "phone": phone, "items": items, "purchase_date": purchase_date}

        now_iso = datetime.now().isoformat()
        log[key]["day1_sent"] = True
        log[key]["day1_sent_at"] = now_iso
        log[key]["day1_send_skipped_by_design"] = True
        log[key]["day3_sent"] = True
        log[key]["day3_sent_at"] = now_iso
        log[key]["backfilled_2026_08_18"] = True
        new_entries += 1

    agent.save_log(log)

    print("\nBackfill complete.")
    print("  New log entries created : {}".format(new_entries))
    print("  Already in log (skipped): {}".format(already_present))
    print("  Bad rows (no phone)     : {}".format(skipped_bad_row))
    print("\nNo WhatsApp messages were sent by this script -- it only wrote to the log.")


if __name__ == "__main__":
    main()
