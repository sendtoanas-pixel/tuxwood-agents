"""
TUXWOOD — Gmail Helper
======================
Fetches the latest Sales Summary Report attachment from Gmail.
Replaces Outlook/win32com for cloud deployment.
Supports both PDF and Excel (.xlsx/.xls) attachments.

Required env vars:
  GMAIL_USER         — sendtoanas@gmail.com
  GMAIL_APP_PASSWORD — Gmail App Password (not your login password)
"""

import imaplib
import email
import os
import tempfile
import pandas as pd
from email.header import decode_header


GMAIL_USER         = os.environ.get("GMAIL_USER", "sendtoanas@gmail.com")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")
SUBJECT_KEYWORD    = "sales report"

ALLOWED_EXTENSIONS = (".pdf", ".xlsx", ".xls")


def fetch_report_from_gmail():
    if not GMAIL_APP_PASSWORD:
        print("⚠️  GMAIL_APP_PASSWORD not set. Skipping Gmail fetch.")
        return None

    try:
        print("📧 Connecting to Gmail to fetch latest sales report...")
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        mail.select("inbox")

        _, data = mail.search(None, f'(SUBJECT "{SUBJECT_KEYWORD}")')
        mail_ids = data[0].split()

        if not mail_ids:
            print("⚠️  No 'sales report' email found in Gmail inbox.")
            mail.logout()
            return None

        latest_id = mail_ids[-1]
        _, msg_data = mail.fetch(latest_id, "(RFC822)")
        raw_email = msg_data[0][1]
        msg = email.message_from_bytes(raw_email)

        for part in msg.walk():
            content_disposition = str(part.get("Content-Disposition", ""))
            if "attachment" in content_disposition:
                filename = part.get_filename()
                if filename and filename.lower().endswith(ALLOWED_EXTENSIONS):
                    decoded = decode_header(filename)
                    fname = decoded[0][0]
                    if isinstance(fname, bytes):
                        fname = fname.decode()

                    ext = ".pdf" if filename.lower().endswith(".pdf") else ".xlsx"

                    tmp = tempfile.NamedTemporaryFile(
                        delete=False,
                        suffix=ext,
                        prefix="sales_report_"
                    )
                    tmp.write(part.get_payload(decode=True))
                    tmp.close()
                    print(f"✅ Downloaded from Gmail: {fname} → {tmp.name}")
                    mail.logout()
                    return tmp.name

        print("⚠️  Email found but no PDF or Excel attachment in it.")
        mail.logout()
        return None

    except Exception as e:
        print(f"❌ Gmail error: {e}")
        return None


def read_sales_report(file_path):
    if not file_path:
        return pd.DataFrame()

    if file_path.lower().endswith(".pdf"):
        return _read_pdf_report(file_path)
    else:
        return pd.read_excel(file_path)


def _read_pdf_report(file_path):
    try:
        import pdfplumber

        all_rows = []
        headers = None

        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                tables = page.extract_tables()
                for table in tables:
                    if not table:
                        continue

                    if headers is None:
                        headers = [str(h).strip() if h else "" for h in table[0]]
                        for row in table[1:]:
                            if any(cell for cell in row):
                                all_rows.append([str(c).strip() if c else "" for c in row])
                    else:
                        for row in table:
                            row_clean = [str(c).strip() if c else "" for c in row]
                            if row_clean == headers:
                                continue
                            if any(cell for cell in row_clean):
                                all_rows.append(row_clean)

        if headers and all_rows:
            df = pd.DataFrame(all_rows, columns=headers)
            for col in df.columns:
                try:
                    df[col] = pd.to_numeric(df[col])
                except (ValueError, TypeError):
                    pass
            print(f"✅ PDF parsed: {len(df)} rows, columns: {list(df.columns)}")
            return df

        print("⚠️  No tables found in PDF.")
        return pd.DataFrame()

    except ImportError:
        print("❌ pdfplumber not installed. Run: pip install pdfplumber")
        return pd.DataFrame()
    except Exception as e:
        print(f"❌ PDF parsing error: {e}")
        return pd.DataFrame()
