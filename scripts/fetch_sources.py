"""Fetch the external evidence datasets used to score careers.

The Microsoft dataset is CC BY 4.0 and is vendored in data/sources/. The AIOE
appendix carries no redistribution licence, so it is downloaded on demand and
kept out of version control (see .gitignore).

Usage: python scripts/fetch_sources.py
"""
from __future__ import annotations

import csv
import sys
import urllib.request
from pathlib import Path
from time import sleep

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "cache"
AIOE_URL = "https://raw.githubusercontent.com/AIOE-Data/AIOE/main/AIOE_DataAppendix.xlsx"
AIOE_XLSX = CACHE / "AIOE_DataAppendix.xlsx"
AIOE_CSV = CACHE / "aioe_appendix_a.csv"


def download(url: str, target: Path, attempts: int = 5) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    last: Exception | None = None
    for attempt in range(attempts):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "will-ai-take-my-job/1.0"})
            target.write_bytes(urllib.request.urlopen(request, timeout=90).read())
            print(f"downloaded {target.name} ({target.stat().st_size} bytes)")
            return
        except Exception as error:  # noqa: BLE001 - report and retry
            last = error
            sleep(2 + 2 * attempt)
    raise SystemExit(f"could not download {url}: {last}")


def extract_aioe() -> None:
    try:
        import openpyxl
    except ImportError:
        raise SystemExit("openpyxl is required: pip install -r requirements.txt")

    workbook = openpyxl.load_workbook(AIOE_XLSX, read_only=True, data_only=True)
    rows = list(workbook["Appendix A"].iter_rows(values_only=True))
    header = rows[0]
    if not header or "SOC" not in str(header[0]).upper():
        raise SystemExit("unexpected AIOE appendix layout")
    with AIOE_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["soc_code", "title", "aioe"])
        written = 0
        for soc, title, score in ((r[0], r[1], r[2]) for r in rows[1:] if r and r[0]):
            writer.writerow([soc, title, score])
            written += 1
    print(f"wrote {AIOE_CSV.name} ({written} occupations)")


def main() -> int:
    if not AIOE_XLSX.exists():
        download(AIOE_URL, AIOE_XLSX)
    else:
        print(f"{AIOE_XLSX.name} already cached")
    extract_aioe()
    print("\nVendored (CC BY 4.0, already in data/sources/):")
    for name in sorted(p.name for p in (ROOT / "data" / "sources").glob("*.csv")):
        print(f"  {name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
