"""
TUXWOOD — One-time patch: protect the 132 log entries the 19:00 (2026-08-18)
cron run registered from a cumulative "Sales Summary Report 3_2026-07-01_
2026-08-18.xlsx" export, so they don't fire a real Day 5 WhatsApp review
request on a future run.
=============================================================================
Why this exists: Muhammed emailed himself a report titled just "sales
report" (not "Backfill ...") whose attachment actually covered Jul 1 - Aug
18 (48 days). tuxwood_purchase_agent.py's Gmail path has no cumulative-
export guard (that protection only exists on the Downloads-folder fallback
path), so the 19:00 UTC run on 2026-08-18 treated it as a normal report and
silently registered all 132 new rows as day1_thankyou (no message sent --
that part was already safe by design). But some of those purchase dates
fall within the last 18 days, so STEP 2 of the NEXT run would have queued
and actually SENT the Day 5 Google-review WhatsApp template to them. The
cron was paused (cronSchedule set to once-a-year) immediately after this was
discovered, before that next run could fire.

WHAT THIS SCRIPT DOES:
  Finds every log entry whose day1_sent_at timestamp falls in the narrow
  window of the 19:00 run (2026-08-18T19:00:1... / 19:00:2...) and which
  doesn't already have day3_sent set, and marks day3_sent = True (with a
  protected_from_cumulative_report_2026_08_18 audit flag) so Day 5 can never
  fire for them. Entries from any other run (past or future) are untouched
  -- this only targets that one specific accidental batch.

  Contains ZERO calls to send_whatsapp / send_whatsapp_template.

HOW TO RUN (one-time, on Railway):
  Temporarily set this service's start command to:
    python patch_protect_cumulative_run.py
  Redeploy, check the logs for the summary line, then set the start command
  back to "python tuxwood_purchase_agent.py --auto", restore cronSchedule to
  "*/15 * * * *", and redeploy again.
"""

from datetime import datetime

import tuxwood_purchase_agent as agent

# The 19:00 run's day1_sent_at timestamps all start with this prefix
# (confirmed from Railway deploy logs: run started 2026-08-18T19:00:11Z,
# finished 2026-08-18T19:00:20Z).
TARGET_PREFIX = "2026-08-18T19:00:1"
TARGET_PREFIX_2 = "2026-08-18T19:00:2"


def main():
    print("=" * 60)
    print("  TUXWOOD -- Protect entries from the 19:00 cumulative-report run")
    print("  {}".format(datetime.now().strftime("%Y-%m-%d %H:%M")))
    print("=" * 60)

    log = agent.load_log()
    patched = 0
    already_protected = 0
    checked = 0

    for key, entry in log.items():
        if not isinstance(entry, dict):
            continue
        sent_at = entry.get("day1_sent_at", "")
        if not (sent_at.startswith(TARGET_PREFIX) or sent_at.startswith(TARGET_PREFIX_2)):
            continue
        checked += 1
        if entry.get("day3_sent"):
            already_protected += 1
            continue
        entry["day3_sent"] = True
        entry["day3_sent_at"] = datetime.now().isoformat()
        entry["protected_from_cumulative_report_2026_08_18"] = True
        patched += 1

    agent.save_log(log)

    print("\nDone.")
    print("  Entries matching the 19:00 run  : {}".format(checked))
    print("  Newly protected (day3_sent set) : {}".format(patched))
    print("  Already had day3_sent           : {}".format(already_protected))
    print("\nNo WhatsApp messages were sent by this script -- it only wrote to the log.")


if __name__ == "__main__":
    main()
