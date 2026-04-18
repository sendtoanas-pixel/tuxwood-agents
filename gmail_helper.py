"""
TUXWOOD — Gmail Helper
======================
Fetches the latest Sales Summary Report attachment from Gmail.
Replaces Outlook/win32com for cloud deployment.

Required env vars:
  GMAIL_USER         — sendtoanas@gmail.com
  GMAIL_APP_PASSWORD — Gmail App Password (not your login password)
"""

import imaplib
import email
import os
import tempfile
from email.header import decode_header


GMAIL_USER         = os.environ.get("GMAIL_USER", "sendtoanas@gmail.com")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")
SUBJECT_KEYWORD    = "sales report"


def fetch_report_from_gmail():
    """
    Connects to Gmail, finds the latest email with 'sales report' in subject,
    downloads the Excel attachment to a temp file, and returns the file path.
    Returns None if not found.
    """
    if not GMAIL_APP_PASSWORD:
        print("⚠️  GMAIL_APP_PASSWORD not set. Skipping Gmail fetch.")
        return None

    try:
        print("📧 Connecting to Gmail to fetch latest sales report...")
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        mail.select("inbox")

        # Search for emails with "sales report" in subject
        _, data = mail.search(None, f'(SUBJECT "{SUBJECT_KEYWORD}")')
        mail_ids = data[0].split()

        if not mail_ids:
            print("⚠️  No 'sales report' email found in Gmail inbox.")
            mail.logout()
            return None

        # Get the latest one
        latest_id = mail_ids[-1]
        _, msg_data = mail.fetch(latest_id, "(RFC822)")
        raw_email = msg_data[0][1]
        msg = email.message_from_bytes(raw_email)

        # Walk through attachments
        for part in msg.walk():
            content_disposition = str(part.get("Content-Disposition", ""))
            if "attachment" in content_disposition:
                filename = part.get_filename()
                if filename and filename.lower().endswith((".xlsx", ".xls")):
                    # Decode filename if needed
                    decoded = decode_header(filename)
                    fname = decoded[0][0]
                    if isinstance(fname, bytes):
                        fname = fname.decode()

                    # Save to temp file
                    tmp = tempfile.NamedTemporaryFile(
                        delete=False,
                        suffix=".xlsx",
                        prefix="sales_report_"
                    )
                    tmp.write(part.get_payload(decode=True))
                    tmp.close()
                    print(f"✅ Downloaded from Gmail: {fname}")
                    mail.logout()
                    return tmp.name

        print("⚠️  Email found but no Excel attachment in it.")
        mail.logout()
        return None

    except Exception as e:
        print(f"❌ Gmail error: {e}")
        return None
