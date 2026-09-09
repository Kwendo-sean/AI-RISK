"""Export scan leads to an Excel workbook for follow-up email campaigns.

By default only rows where the person ticked the marketing consent box are
exported. Pass --all to include everyone who asked for their results by email
(use that for support or debugging, not for bulk mail).

Usage:
    python scripts/export_leads.py                    # consented leads -> leads.xlsx
    python scripts/export_leads.py --days 30          # last 30 days only
    python scripts/export_leads.py --all -o audit.xlsx
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import platform_db  # noqa: E402

COLUMNS = [
    ("created_at", "Scanned (UTC)"),
    ("email", "Email"),
    ("first_name", "First name"),
    ("career_title", "Career"),
    ("industry", "Industry"),
    ("region", "Region"),
    ("career_stage", "Career stage"),
    ("ai_exposure", "AI exposure (0-100)"),
    ("augmentation_potential", "Augmentation (0-100)"),
    ("transformation_pressure", "Pressure (0-100)"),
    ("overall_status", "Status"),
    ("rank", "Rank"),
    ("xp", "XP"),
    ("marketing_consent", "Consented"),
    ("consent_at", "Consented at (UTC)"),
    ("top_skill", "First recommended skill"),
]


def _top_skill(row: dict) -> str:
    try:
        result = json.loads(row.get("result_json") or "{}")
        return (result.get("skill_recommendations") or [{}])[0].get("name", "")
    except (ValueError, TypeError, IndexError, AttributeError):
        return ""


def _stamp(value) -> str:
    if not value:
        return ""
    return time.strftime("%Y-%m-%d %H:%M", time.gmtime(int(value)))


async def collect(consented_only: bool, since: int | None) -> list[dict]:
    await platform_db.init_platform_db()
    try:
        return await platform_db.list_scan_leads(consented_only=consented_only, since=since)
    finally:
        await platform_db.close_platform_db()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("-o", "--output", default="leads.xlsx", help="output .xlsx path (default: leads.xlsx)")
    parser.add_argument("--all", action="store_true", help="include leads without marketing consent")
    parser.add_argument("--days", type=int, default=0, help="only leads from the last N days")
    args = parser.parse_args()

    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font
    except ImportError:
        print("openpyxl is required: pip install -r requirements.txt", file=sys.stderr)
        return 1

    since = int(time.time()) - args.days * 86400 if args.days else None
    rows = asyncio.run(collect(consented_only=not args.all, since=since))

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Leads"
    sheet.append([label for _, label in COLUMNS])
    for cell in sheet[1]:
        cell.font = Font(bold=True)
    sheet.freeze_panes = "A2"

    for row in rows:
        values = []
        for key, _ in COLUMNS:
            if key == "top_skill":
                values.append(_top_skill(row))
            elif key in {"created_at", "consent_at"}:
                values.append(_stamp(row.get(key)))
            elif key == "marketing_consent":
                values.append("yes" if row.get(key) else "no")
            else:
                values.append(row.get(key))
        sheet.append(values)

    widths = {"B": 32, "C": 16, "D": 30, "E": 24, "F": 18, "G": 20, "A": 18, "P": 34, "L": 14}
    for column, width in widths.items():
        sheet.column_dimensions[column].width = width

    output = Path(args.output)
    workbook.save(output)
    scope = "all leads" if args.all else "consented leads"
    window = f", last {args.days} days" if args.days else ""
    print(f"wrote {output} - {len(rows)} rows ({scope}{window}, backend: {platform_db.backend_name()})")
    if not args.all:
        print("Only people who ticked the consent box are included. Do not bulk-mail the --all export.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
