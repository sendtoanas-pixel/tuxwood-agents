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
    """
    Connects to Gmail, finds the latest email with 'sales report' in subject,
    downloads the PDF or Excel attachment to a temp file, and returns the file path.
    Returns None if not found.
    """
    result = fetch_new_report_from_gmail(unread_only=False)
    if result:
        return result[0]
    return None


def fetch_new_report_from_gmail(unread_only=True):
    """
    Connects to Gmail, finds NEW (unread) emails with 'sales report' in subject.
    Downloads the attachment, marks the email as READ to avoid reprocessing.
    Returns (file_path, email_uid) tuple, or None if no new report found.

    Set unread_only=False to fetch the latest report regardless of read status.
    """
    if not GMAIL_APP_PASSWORD:
        print("⚠️  GMAIL_APP_PASSWORD not set. Skipping Gmail fetch.")
        return None

    try:
        print("📧 Connecting to Gmail to fetch sales report...")
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        mail.select("inbox")

        # Search for UNSEEN or ALL emails with "sales report" in subject
        if unread_only:
            search_query = f'(UNSEEN SUBJECT "{SUBJECT_KEYWORD}")'
        else:
            search_query = f'(SUBJECT "{SUBJECT_KEYWORD}")'

        _, data = mail.search(None, search_query)
        mail_ids = data[0].split()

        if not mail_ids:
            if unread_only:
                print("✅ No new (unread) sales report emails. Nothing to process.")
            else:
                print("⚠️  No 'sales report' email found in Gmail inbox.")
            mail.logout()
            return None

        # Get the latest one
        latest_id = mail_ids[-1]
        email_uid = latest_id.decode()
        _, msg_data = mail.fetch(latest_id, "(RFC822)")
        raw_email = msg_data[0][1]
        msg = email.message_from_bytes(raw_email)

        # Walk through attachments — accept PDF or Excel
        for part in msg.walk():
            content_disposition = str(part.get("Content-Disposition", ""))
            if "attachment" in content_disposition:
                filename = part.get_filename()
                if filename and filename.lower().endswith(ALLOWED_EXTENSIONS):
                    # Decode filename if needed
                    decoded = decode_header(filename)
                    fname = decoded[0][0]
                    if isinstance(fname, bytes):
                        fname = fname.decode()

                    # Determine suffix
                    ext = ".pdf" if filename.lower().endswith(".pdf") else ".xlsx"

                    # Save to temp file
                    tmp = tempfile.NamedTemporaryFile(
                        delete=False,
                        suffix=ext,
                        prefix="sales_report_"
                    )
                    tmp.write(part.get_payload(decode=True))
                    tmp.close()

                    # Mark email as READ so it won't be fetched again
                    if unread_only:
                        mail.store(latest_id, "+FLAGS", "\\Seen")

                    print(f"✅ Downloaded from Gmail: {fname} → {tmp.name}")
                    mail.logout()
                    return (tmp.name, email_uid)

        print("⚠️  Email found but no PDF or Excel attachment in it.")
        mail.logout()
        return None

    except Exception as e:
        print(f"❌ Gmail error: {e}")
        return None


def read_sales_report(file_path):
    """
    Reads a sales report file (PDF or Excel) into a pandas DataFrame.
    Use this in all agents instead of pd.read_excel() directly.
    """
    if not file_path:
        return pd.DataFrame()

    if file_path.lower().endswith(".pdf"):
        return _read_pdf_report(file_path)
    else:
        return pd.read_excel(file_path)


def _read_pdf_report(file_path):
    """
    Extracts table data from a PDF sales report using pdfplumber.
    Handles multi-page PDFs, title rows, and repeated header rows.
    Automatically finds the real header row containing 'Customer Name'.
    """
    try:
        import pdfplumber

        all_rows = []
        headers = None

        # Key columns we expect in the real header row
        HEADER_KEYWORDS = ["customer", "mobile", "name", "phone", "item", "amount", "date"]

        def is_real_header(row):
            """Check if this row looks like the actual column header row."""
            row_text = " ".join([str(c).lower().strip() for c in row if c])
            return any(kw in row_text for kw in HEADER_KEYWORDS)

        def is_empty_row(row):
            return not any(str(c).strip() for c in row if c)

        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                tables = page.extract_tables()
                for table in tables:
                    if not table:
                        continue

                    if headers is None:
                        # Search for the real header row (skip title rows)
                        header_idx = None
                        for i, row in enumerate(table):
                            if is_real_header(row):
                                header_idx = i
                                break

                        if header_idx is None:
                            # Fallback: use first row as header
                            header_idx = 0

                        headers = [str(h).strip() if h else f"col_{i}" for i, h in enumerate(table[header_idx])]
                        # Add data rows after header
                        for row in table[header_idx + 1:]:
                            if not is_empty_row(row):
                                all_rows.append([str(c).strip() if c else "" for c in row])
                    else:
                        # Subsequent pages — skip title/header rows
                        for row in table:
                            row_clean = [str(c).strip() if c else "" for c in row]
                            if is_empty_row(row):
                                continue
                            if is_real_header(row):
                                continue  # skip repeated header
                            all_rows.append(row_clean)

        if headers and all_rows:
            df = pd.DataFrame(all_rows, columns=headers)
            # Try to convert numeric columns
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
