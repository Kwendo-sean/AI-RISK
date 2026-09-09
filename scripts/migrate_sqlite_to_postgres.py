"""Copy an existing SQLite database into PostgreSQL.

Used once, during the cutover from the old non-Docker deployment. Reads the SQLite
file directly and inserts into the Postgres tables in dependency order, skipping
rows that are already there, so it is safe to run twice.

Usage:
    python scripts/migrate_sqlite_to_postgres.py --sqlite /tmp/old.db [--dry-run]

DATABASE_URL must point at the target Postgres instance.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Child tables last: every insert must find its parent already present.
TABLES: list[tuple[str, list[str], str]] = [
    ("user_profiles", [
        "session_id", "token_hash", "first_name", "career_id", "custom_career", "career_stage",
        "industry", "region", "education_level", "years_experience", "profile_json",
        "created_at", "updated_at", "expires_at",
    ], "session_id"),
    ("assessment_sessions", [
        "assessment_id", "session_id", "career_snapshot", "question_ids", "status",
        "result_json", "xp", "rank", "created_at", "updated_at",
    ], "assessment_id"),
    ("assessment_answers", [
        "assessment_id", "question_id", "answer_index", "created_at", "updated_at",
    ], "assessment_id, question_id"),
    ("game_events", [
        "event_id", "assessment_id", "event_type", "payload_json", "xp_delta", "created_at",
    ], "event_id"),
    ("analytics_events", [
        "anonymous_id", "event_name", "properties_json", "created_at",
    ], None),
    ("scan_leads", [
        "session_id", "assessment_id", "email", "first_name", "career_id", "career_title",
        "industry", "region", "career_stage", "ai_exposure", "augmentation_potential",
        "transformation_pressure", "overall_status", "rank", "xp", "result_json",
        "marketing_consent", "consent_source", "consent_at", "created_at", "updated_at",
    ], "assessment_id, email"),
    ("email_outbox", [
        "to_email", "subject", "html_body", "text_body", "kind", "status", "attempts",
        "last_error", "provider_message_id", "created_at", "updated_at", "sent_at",
    ], None),
]

BOOLEAN_COLUMNS = {"marketing_consent"}


def read_table(connection: sqlite3.Connection, table: str, columns: list[str]) -> list[tuple]:
    cursor = connection.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
    if not cursor.fetchone():
        return []
    available = {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}
    missing = [c for c in columns if c not in available]
    if missing:
        print(f"  {table}: source is missing {missing}, skipping table")
        return []
    rows = connection.execute(f"SELECT {', '.join(columns)} FROM {table}").fetchall()
    if not BOOLEAN_COLUMNS & set(columns):
        return [tuple(row) for row in rows]
    index = {name: position for position, name in enumerate(columns)}
    converted = []
    for row in rows:
        values = list(row)
        for name in BOOLEAN_COLUMNS & set(columns):
            values[index[name]] = bool(values[index[name]])
        converted.append(tuple(values))
    return converted


async def run(sqlite_path: Path, dry_run: bool) -> int:
    dsn = os.getenv("DATABASE_URL", "").strip()
    if not dsn.startswith(("postgres://", "postgresql://")):
        print("DATABASE_URL must point at PostgreSQL", file=sys.stderr)
        return 1
    if not sqlite_path.exists():
        print(f"no such file: {sqlite_path}", file=sys.stderr)
        return 1

    import asyncpg

    import platform_db

    await platform_db.init_platform_db()  # ensures the schema exists
    await platform_db.close_platform_db()

    source = sqlite3.connect(f"file:{sqlite_path}?mode=ro", uri=True)
    connection = await asyncpg.connect(dsn.replace("postgres://", "postgresql://", 1))
    total = 0
    try:
        for table, columns, conflict in TABLES:
            rows = read_table(source, table, columns)
            if not rows:
                print(f"  {table}: nothing to copy")
                continue
            if dry_run:
                print(f"  {table}: would copy {len(rows)} rows")
                total += len(rows)
                continue
            placeholders = ", ".join(f"${i}" for i in range(1, len(columns) + 1))
            conflict_clause = f"ON CONFLICT ({conflict}) DO NOTHING" if conflict else "ON CONFLICT DO NOTHING"
            statement = f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders}) {conflict_clause}"
            copied = 0
            async with connection.transaction():
                for row in rows:
                    status = await connection.execute(statement, *row)
                    copied += 1 if status.endswith("1") else 0
            print(f"  {table}: {copied} inserted, {len(rows) - copied} already present")
            total += copied
    finally:
        source.close()
        await connection.close()

    print(f"{'would copy' if dry_run else 'copied'} {total} rows")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sqlite", required=True, type=Path, help="path to the old willaijob.db")
    parser.add_argument("--dry-run", action="store_true", help="report what would be copied")
    args = parser.parse_args()
    return asyncio.run(run(args.sqlite, args.dry_run))


if __name__ == "__main__":
    raise SystemExit(main())
