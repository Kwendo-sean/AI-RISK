"""Send whatever is sitting in the email outbox, then exit.

The app flushes the outbox on a timer while it runs. This script exists for the
offline case: a deployment with no internet (the Raspberry Pi) queues mail
locally, and you run this from a machine that can reach Resend - or on the Pi
itself once it is connected - to drain the queue.

Usage:
    python scripts/flush_emails.py              # one pass
    python scripts/flush_emails.py --watch 60   # keep flushing every 60s
    python scripts/flush_emails.py --status     # just report the queue
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import platform_db  # noqa: E402
import platform_email  # noqa: E402


async def run(watch: int, status_only: bool) -> int:
    await platform_db.init_platform_db()
    try:
        stats = await platform_db.outbox_stats()
        print(f"outbox ({platform_db.backend_name()}): " + (", ".join(f"{k}={v}" for k, v in sorted(stats.items())) or "empty"))
        if status_only:
            return 0
        if not platform_email.delivery_enabled():
            print("RESEND_API_KEY is not set - nothing can be sent from here.")
            return 1
        while True:
            counts = await platform_email.flush_once(limit=50)
            print(f"sent={counts['sent']} retrying={counts['skipped']} failed={counts['failed']}")
            if not watch:
                break
            await asyncio.sleep(watch)
        return 0
    finally:
        await platform_db.close_platform_db()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--watch", type=int, default=0, metavar="SECONDS", help="keep flushing on an interval")
    parser.add_argument("--status", action="store_true", help="report queue counts and exit")
    args = parser.parse_args()
    try:
        return asyncio.run(run(args.watch, args.status))
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
