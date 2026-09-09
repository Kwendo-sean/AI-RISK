"""Async PostgreSQL backend.

This is the production store. It exposes exactly the same functions as db_sqlite so
platform_db can pick a backend at start-up without the API layer knowing which one it
got. Unlike SQLite there is no single-writer bottleneck, so writes go straight to the
pool instead of through a batching queue.

Connection budget: pool_max per worker x workers must stay under the server's
max_connections. See docs/DEPLOYMENT.md for the sizing used at 200+ concurrent users.
"""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import time
import uuid
from pathlib import Path
from typing import Any

import asyncpg

MIGRATIONS_DIR = Path(__file__).parent / "migrations" / "postgres"
PROFILE_TTL_SECONDS = int(os.getenv("PROFILE_TTL_DAYS", "90")) * 86400

_pool: asyncpg.Pool | None = None
_dsn: str = ""


def set_dsn(dsn: str) -> None:
    global _dsn
    # asyncpg wants postgresql://, but platform-as-a-service providers hand out postgres://
    _dsn = dsn.replace("postgres://", "postgresql://", 1) if dsn.startswith("postgres://") else dsn


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _pool_or_raise() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("PostgreSQL pool is not initialised")
    return _pool


async def init_platform_db() -> None:
    global _pool
    await close_platform_db()
    _pool = await asyncpg.create_pool(
        dsn=_dsn or os.getenv("DATABASE_URL", ""),
        min_size=int(os.getenv("PG_POOL_MIN", "2")),
        max_size=int(os.getenv("PG_POOL_MAX", "12")),
        command_timeout=float(os.getenv("PG_COMMAND_TIMEOUT", "10")),
        max_inactive_connection_lifetime=float(os.getenv("PG_MAX_IDLE_SECONDS", "300")),
        statement_cache_size=int(os.getenv("PG_STATEMENT_CACHE", "256")),
    )
    async with _pool.acquire() as connection:
        # Advisory lock: with several workers booting at once only one runs migrations.
        await connection.execute("SELECT pg_advisory_lock($1)", 4_242_424_242)
        try:
            await connection.execute(
                "CREATE TABLE IF NOT EXISTS schema_migrations (version TEXT PRIMARY KEY, "
                "applied_at BIGINT NOT NULL DEFAULT EXTRACT(EPOCH FROM now())::bigint)"
            )
            for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
                version = path.stem
                applied = await connection.fetchval("SELECT 1 FROM schema_migrations WHERE version=$1", version)
                if applied:
                    continue
                async with connection.transaction():
                    await connection.execute(path.read_text(encoding="utf-8"))
                    await connection.execute("INSERT INTO schema_migrations(version) VALUES ($1)", version)
        finally:
            await connection.execute("SELECT pg_advisory_unlock($1)", 4_242_424_242)


async def close_platform_db() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


# ── Profiles ─────────────────────────────────────────────────────────────────

async def create_profile(profile: dict[str, Any]) -> dict[str, str]:
    session_id = str(uuid.uuid4())
    token = secrets.token_urlsafe(32)
    now = int(time.time())
    await _pool_or_raise().execute(
        """INSERT INTO user_profiles
            (session_id, token_hash, first_name, career_id, custom_career, career_stage, industry, region,
             education_level, years_experience, profile_json, created_at, updated_at, expires_at)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14)""",
        session_id, hash_token(token), profile["first_name"], profile.get("career_id"), profile.get("custom_career"),
        profile["career_stage"], profile["industry"], profile.get("region"), profile.get("education_level"),
        profile.get("years_experience"), json.dumps(profile), now, now, now + PROFILE_TTL_SECONDS,
    )
    return {"session_id": session_id, "access_token": token}


async def get_profile(session_id: str, token: str) -> dict[str, Any] | None:
    row = await _pool_or_raise().fetchrow(
        "SELECT * FROM user_profiles WHERE session_id=$1 AND token_hash=$2 AND expires_at>$3",
        session_id, hash_token(token), int(time.time()),
    )
    return dict(row) if row else None


async def update_profile(session_id: str, token: str, profile: dict[str, Any]) -> bool:
    now = int(time.time())
    status = await _pool_or_raise().execute(
        """UPDATE user_profiles SET first_name=$1, career_id=$2, custom_career=$3, career_stage=$4, industry=$5,
            region=$6, education_level=$7, years_experience=$8, profile_json=$9, updated_at=$10, expires_at=$11
        WHERE session_id=$12 AND token_hash=$13""",
        profile["first_name"], profile.get("career_id"), profile.get("custom_career"), profile["career_stage"],
        profile["industry"], profile.get("region"), profile.get("education_level"), profile.get("years_experience"),
        json.dumps(profile), now, now + PROFILE_TTL_SECONDS, session_id, hash_token(token),
    )
    return status.endswith("1")


async def delete_profile(session_id: str, token: str) -> bool:
    status = await _pool_or_raise().execute(
        "DELETE FROM user_profiles WHERE session_id=$1 AND token_hash=$2", session_id, hash_token(token)
    )
    return status.endswith("1")


# ── Assessments ──────────────────────────────────────────────────────────────

async def create_assessment(session_id: str, career: dict[str, Any], question_ids: list[str]) -> str:
    assessment_id = str(uuid.uuid4())
    await _pool_or_raise().execute(
        "INSERT INTO assessment_sessions(assessment_id, session_id, career_snapshot, question_ids, status) "
        "VALUES ($1,$2,$3,$4,'active')",
        assessment_id, session_id, json.dumps(career), json.dumps(question_ids),
    )
    return assessment_id


async def get_assessment(assessment_id: str, session_id: str) -> dict[str, Any] | None:
    pool = _pool_or_raise()
    async with pool.acquire() as connection:
        row = await connection.fetchrow(
            "SELECT * FROM assessment_sessions WHERE assessment_id=$1 AND session_id=$2", assessment_id, session_id
        )
        if not row:
            return None
        answers = await connection.fetch(
            "SELECT question_id, answer_index FROM assessment_answers WHERE assessment_id=$1", assessment_id
        )
    result = dict(row)
    result["career"] = json.loads(result.pop("career_snapshot"))
    result["question_ids"] = json.loads(result["question_ids"])
    result["answers"] = {r["question_id"]: r["answer_index"] for r in answers}
    result["result"] = json.loads(result["result_json"]) if result.get("result_json") else None
    return result


async def get_latest_assessment(session_id: str) -> dict[str, Any] | None:
    row = await _pool_or_raise().fetchrow(
        "SELECT assessment_id FROM assessment_sessions WHERE session_id=$1 ORDER BY updated_at DESC LIMIT 1",
        session_id,
    )
    return await get_assessment(row["assessment_id"], session_id) if row else None


async def save_answer(assessment_id: str, question_id: str, answer_index: int, question_ids: list[str]) -> None:
    pool = _pool_or_raise()
    async with pool.acquire() as connection, connection.transaction():
        await connection.execute(
            """INSERT INTO assessment_answers(assessment_id, question_id, answer_index) VALUES ($1,$2,$3)
            ON CONFLICT (assessment_id, question_id) DO UPDATE
                SET answer_index=EXCLUDED.answer_index, updated_at=EXTRACT(EPOCH FROM now())::bigint""",
            assessment_id, question_id, answer_index,
        )
        await connection.execute(
            "UPDATE assessment_sessions SET question_ids=$1, updated_at=EXTRACT(EPOCH FROM now())::bigint "
            "WHERE assessment_id=$2",
            json.dumps(question_ids), assessment_id,
        )


async def complete_assessment(assessment_id: str, result: dict[str, Any], xp: int, rank: str) -> None:
    await _pool_or_raise().execute(
        "UPDATE assessment_sessions SET status='complete', result_json=$1, xp=$2, rank=$3, "
        "updated_at=EXTRACT(EPOCH FROM now())::bigint WHERE assessment_id=$4",
        json.dumps(result), xp, rank, assessment_id,
    )


async def record_game_event(assessment_id: str, event_id: str, event_type: str, payload: dict[str, Any], xp_delta: int) -> bool:
    pool = _pool_or_raise()
    async with pool.acquire() as connection, connection.transaction():
        status = await connection.execute(
            "INSERT INTO game_events(event_id, assessment_id, event_type, payload_json, xp_delta) "
            "VALUES ($1,$2,$3,$4,$5) ON CONFLICT (event_id) DO NOTHING",
            event_id, assessment_id, event_type, json.dumps(payload), xp_delta,
        )
        created = status.endswith("1")
        if created:
            await connection.execute(
                "UPDATE assessment_sessions SET xp=xp+$1, updated_at=EXTRACT(EPOCH FROM now())::bigint "
                "WHERE assessment_id=$2",
                xp_delta, assessment_id,
            )
    return created


async def record_analytics(anonymous_id: str, event_name: str, properties: dict[str, Any]) -> None:
    await _pool_or_raise().execute(
        "INSERT INTO analytics_events(anonymous_id, event_name, properties_json) VALUES ($1,$2,$3)",
        anonymous_id, event_name, json.dumps(properties),
    )


# ── Scan leads and email outbox ──────────────────────────────────────────────

async def record_scan_lead(lead: dict[str, Any]) -> int | None:
    now = int(time.time())
    return await _pool_or_raise().fetchval(
        """INSERT INTO scan_leads(session_id, assessment_id, email, first_name, career_id, career_title,
            industry, region, career_stage, ai_exposure, augmentation_potential, transformation_pressure,
            overall_status, rank, xp, result_json, marketing_consent, consent_source, consent_at, updated_at)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20)
        ON CONFLICT (assessment_id, email) DO UPDATE SET
            ai_exposure=EXCLUDED.ai_exposure, augmentation_potential=EXCLUDED.augmentation_potential,
            transformation_pressure=EXCLUDED.transformation_pressure, overall_status=EXCLUDED.overall_status,
            rank=EXCLUDED.rank, xp=EXCLUDED.xp, result_json=EXCLUDED.result_json,
            marketing_consent=EXCLUDED.marketing_consent, consent_source=EXCLUDED.consent_source,
            consent_at=COALESCE(scan_leads.consent_at, EXCLUDED.consent_at), updated_at=EXCLUDED.updated_at
        RETURNING id""",
        lead.get("session_id"), lead.get("assessment_id"), lead["email"], lead.get("first_name"),
        lead.get("career_id"), lead.get("career_title"), lead.get("industry"), lead.get("region"),
        lead.get("career_stage"), lead.get("ai_exposure"), lead.get("augmentation_potential"),
        lead.get("transformation_pressure"), lead.get("overall_status"), lead.get("rank"), lead.get("xp"),
        json.dumps(lead.get("result") or {}), bool(lead.get("marketing_consent")), lead.get("consent_source"),
        now if lead.get("marketing_consent") else None, now,
    )


async def queue_email(lead_id: int | None, to_email: str, subject: str, html_body: str, text_body: str | None, kind: str = "results") -> int | None:
    return await _pool_or_raise().fetchval(
        "INSERT INTO email_outbox(lead_id, to_email, subject, html_body, text_body, kind) "
        "VALUES ($1,$2,$3,$4,$5,$6) RETURNING id",
        lead_id, to_email, subject, html_body, text_body, kind,
    )


async def claim_queued_emails(limit: int = 20) -> list[dict[str, Any]]:
    """Claim a batch atomically so multiple workers never send the same email twice."""
    rows = await _pool_or_raise().fetch(
        """UPDATE email_outbox SET status='sending', attempts=attempts+1,
                updated_at=EXTRACT(EPOCH FROM now())::bigint
        WHERE id IN (
            SELECT id FROM email_outbox WHERE status='queued'
            ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT $1
        )
        RETURNING *""",
        limit,
    )
    return [dict(row) for row in rows]


async def finish_email(email_id: int, status: str, provider_message_id: str | None = None, error: str | None = None) -> None:
    await _pool_or_raise().execute(
        """UPDATE email_outbox SET status=$1, provider_message_id=$2, last_error=$3,
            updated_at=EXTRACT(EPOCH FROM now())::bigint,
            sent_at=CASE WHEN $1='sent' THEN EXTRACT(EPOCH FROM now())::bigint ELSE sent_at END
        WHERE id=$4""",
        status, provider_message_id, error, email_id,
    )


async def requeue_stalled_emails(older_than_seconds: int = 300) -> int:
    status = await _pool_or_raise().execute(
        "UPDATE email_outbox SET status='queued', updated_at=EXTRACT(EPOCH FROM now())::bigint "
        "WHERE status='sending' AND updated_at < $1",
        int(time.time()) - older_than_seconds,
    )
    return int(status.rsplit(" ", 1)[-1] or 0)


async def list_scan_leads(consented_only: bool = True, since: int | None = None, limit: int = 100000) -> list[dict[str, Any]]:
    clauses, params = [], []
    if consented_only:
        clauses.append("marketing_consent = TRUE")
    if since:
        params.append(since)
        clauses.append(f"created_at >= ${len(params)}")
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    params.append(limit)
    rows = await _pool_or_raise().fetch(
        f"SELECT * FROM scan_leads {where} ORDER BY created_at DESC LIMIT ${len(params)}", *params
    )
    return [dict(row) for row in rows]


async def outbox_stats() -> dict[str, int]:
    rows = await _pool_or_raise().fetch("SELECT status, COUNT(*) AS total FROM email_outbox GROUP BY status")
    return {row["status"]: row["total"] for row in rows}


async def database_health() -> dict[str, Any]:
    started = time.perf_counter()
    try:
        pool = _pool_or_raise()
        value = await pool.fetchval("SELECT 1")
        return {
            "ok": value == 1,
            "latency_ms": round((time.perf_counter() - started) * 1000, 2),
            "engine": "postgres",
            "pool_size": pool.get_size(),
            "pool_idle": pool.get_idle_size(),
        }
    except Exception:
        return {"ok": False, "latency_ms": round((time.perf_counter() - started) * 1000, 2), "engine": "postgres"}
