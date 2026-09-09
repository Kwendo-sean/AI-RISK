"""Async SQLite backend: migrations, pooled reads, batched writes.

Used for local development and for single-node offline deployments (the Raspberry Pi).
Multi-replica production runs on PostgreSQL - see db_postgres.py.
"""

from __future__ import annotations

import hashlib
import asyncio
import json
import os
import secrets
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import aiosqlite

DB_PATH = os.getenv("DB_PATH", "willaijob.db")


def set_db_path(path: str) -> None:
    global DB_PATH
    DB_PATH = path
MIGRATIONS_DIR = Path(__file__).parent / "migrations" / "sqlite"
PROFILE_TTL_SECONDS = int(os.getenv("PROFILE_TTL_DAYS", "90")) * 86400
_write_lock = asyncio.Lock()
_read_pool: asyncio.Queue | None = None
_writer: aiosqlite.Connection | None = None
_answer_queue: asyncio.Queue | None = None
_answer_task: asyncio.Task | None = None
_general_queue: asyncio.Queue | None = None
_general_task: asyncio.Task | None = None


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


async def _new_connection() -> aiosqlite.Connection:
    db = await aiosqlite.connect(DB_PATH, timeout=10)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA foreign_keys=ON")
    await db.execute("PRAGMA busy_timeout=5000")
    await db.execute("PRAGMA synchronous=NORMAL")
    return db


@asynccontextmanager
async def connect():
    if _read_pool is not None:
        db = await _read_pool.get()
        try:
            yield db
        finally:
            _read_pool.put_nowait(db)
        return
    db = await _new_connection()
    try:
        yield db
    finally:
        await db.close()


@asynccontextmanager
async def write_connection():
    # SQLite has one writer. Queue writes inside a process instead of making every
    # request compete until busy_timeout expires. Production multi-replica use is
    # gated separately in deployment guidance.
    async with _write_lock:
        if _writer is not None:
            yield _writer
            return
        async with connect() as db:
            yield db


async def init_platform_db() -> None:
    global _read_pool, _writer, _answer_queue, _answer_task, _general_queue, _general_task
    await close_platform_db()
    db = await _new_connection()
    try:
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("CREATE TABLE IF NOT EXISTS schema_migrations (version TEXT PRIMARY KEY, applied_at INTEGER NOT NULL DEFAULT (unixepoch()))")
        for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
            version = path.stem
            applied = await db.execute_fetchall("SELECT 1 FROM schema_migrations WHERE version=?", (version,))
            if applied:
                continue
            await db.executescript(path.read_text(encoding="utf-8"))
            await db.execute("INSERT INTO schema_migrations(version) VALUES (?)", (version,))
        await db.commit()
    finally:
        await db.close()
    _writer = await _new_connection()
    _read_pool = asyncio.Queue()
    for _ in range(max(2, int(os.getenv("SQLITE_READ_POOL_SIZE", "8")))):
        _read_pool.put_nowait(await _new_connection())
    _answer_queue = asyncio.Queue(maxsize=int(os.getenv("ANSWER_QUEUE_SIZE", "10000")))
    _answer_task = asyncio.create_task(_answer_writer(), name="sqlite-answer-writer")
    _general_queue = asyncio.Queue(maxsize=int(os.getenv("WRITE_QUEUE_SIZE", "10000")))
    _general_task = asyncio.create_task(_general_writer(), name="sqlite-general-writer")


async def close_platform_db() -> None:
    global _read_pool, _writer, _answer_queue, _answer_task, _general_queue, _general_task
    if _answer_queue is not None and _answer_task is not None:
        await _answer_queue.put(None)
        await _answer_task
    _answer_queue = None
    _answer_task = None
    if _general_queue is not None and _general_task is not None:
        await _general_queue.put(None)
        await _general_task
    _general_queue = None
    _general_task = None
    if _writer is not None:
        await _writer.close()
        _writer = None
    if _read_pool is not None:
        while not _read_pool.empty():
            await (await _read_pool.get()).close()
        _read_pool = None


async def create_profile(profile: dict[str, Any]) -> dict[str, str]:
    session_id = str(uuid.uuid4())
    token = secrets.token_urlsafe(32)
    now = int(time.time())
    params = (session_id, hash_token(token), profile["first_name"], profile.get("career_id"), profile.get("custom_career"),
              profile["career_stage"], profile["industry"], profile.get("region"), profile.get("education_level"),
              profile.get("years_experience"), json.dumps(profile), now, now, now + PROFILE_TTL_SECONDS)
    await _enqueue_general("create_profile", params)
    return {"session_id": session_id, "access_token": token}


async def get_profile(session_id: str, token: str) -> dict[str, Any] | None:
    async with connect() as db:
        cursor = await db.execute("SELECT * FROM user_profiles WHERE session_id=? AND token_hash=? AND expires_at>?", (session_id, hash_token(token), int(time.time())))
        row = await cursor.fetchone()
        return dict(row) if row else None


async def update_profile(session_id: str, token: str, profile: dict[str, Any]) -> bool:
    now = int(time.time())
    params = (profile["first_name"], profile.get("career_id"), profile.get("custom_career"), profile["career_stage"], profile["industry"],
              profile.get("region"), profile.get("education_level"), profile.get("years_experience"), json.dumps(profile), now,
              now + PROFILE_TTL_SECONDS, session_id, hash_token(token))
    return bool(await _enqueue_general("update_profile", params))


async def delete_profile(session_id: str, token: str) -> bool:
    return bool(await _enqueue_general("delete_profile", (session_id, hash_token(token))))


async def create_assessment(session_id: str, career: dict[str, Any], question_ids: list[str]) -> str:
    assessment_id = str(uuid.uuid4())
    await _enqueue_general("create_assessment", (assessment_id, session_id, json.dumps(career), json.dumps(question_ids)))
    return assessment_id


async def get_assessment(assessment_id: str, session_id: str) -> dict[str, Any] | None:
    async with connect() as db:
        cursor = await db.execute("SELECT * FROM assessment_sessions WHERE assessment_id=? AND session_id=?", (assessment_id, session_id))
        row = await cursor.fetchone()
        if not row:
            return None
        answers_cursor = await db.execute("SELECT question_id, answer_index FROM assessment_answers WHERE assessment_id=?", (assessment_id,))
        answers = {r["question_id"]: r["answer_index"] for r in await answers_cursor.fetchall()}
        result = dict(row)
        result["career"] = json.loads(result.pop("career_snapshot"))
        result["question_ids"] = json.loads(result["question_ids"])
        result["answers"] = answers
        result["result"] = json.loads(result["result_json"]) if result.get("result_json") else None
        return result


async def get_latest_assessment(session_id: str) -> dict[str, Any] | None:
    async with connect() as db:
        cursor = await db.execute("SELECT assessment_id FROM assessment_sessions WHERE session_id=? ORDER BY updated_at DESC LIMIT 1", (session_id,))
        row = await cursor.fetchone()
    return await get_assessment(row["assessment_id"], session_id) if row else None


async def save_answer(assessment_id: str, question_id: str, answer_index: int, question_ids: list[str]) -> None:
    if _answer_queue is not None:
        future = asyncio.get_running_loop().create_future()
        await _answer_queue.put((assessment_id, question_id, answer_index, json.dumps(question_ids), future))
        await future
        return
    async with write_connection() as db:
        await db.execute("BEGIN IMMEDIATE")
        await db.execute(
            """INSERT INTO assessment_answers(assessment_id, question_id, answer_index) VALUES (?, ?, ?)
            ON CONFLICT(assessment_id, question_id) DO UPDATE SET answer_index=excluded.answer_index, updated_at=unixepoch()""",
            (assessment_id, question_id, answer_index),
        )
        await db.execute("UPDATE assessment_sessions SET question_ids=?, updated_at=unixepoch() WHERE assessment_id=?", (json.dumps(question_ids), assessment_id))
        await db.commit()


async def _answer_writer() -> None:
    """Commit concurrent answer updates in short batches to reduce SQLite fsync pressure."""
    while True:
        first = await _answer_queue.get()
        if first is None:
            return
        batch = [first]
        await asyncio.sleep(float(os.getenv("ANSWER_BATCH_WINDOW_MS", "8")) / 1000)
        while len(batch) < 500:
            try:
                item = _answer_queue.get_nowait()
            except asyncio.QueueEmpty:
                break
            if item is None:
                await _answer_queue.put(None)
                break
            batch.append(item)
        try:
            async with write_connection() as db:
                await db.execute("BEGIN IMMEDIATE")
                for assessment_id, question_id, answer_index, question_ids_json, _ in batch:
                    await db.execute(
                        """INSERT INTO assessment_answers(assessment_id, question_id, answer_index) VALUES (?, ?, ?)
                        ON CONFLICT(assessment_id, question_id) DO UPDATE SET answer_index=excluded.answer_index, updated_at=unixepoch()""",
                        (assessment_id, question_id, answer_index),
                    )
                    await db.execute("UPDATE assessment_sessions SET question_ids=?, updated_at=unixepoch() WHERE assessment_id=?", (question_ids_json, assessment_id))
                await db.commit()
            for *_, future in batch:
                if not future.done():
                    future.set_result(None)
        except Exception as exc:
            for *_, future in batch:
                if not future.done():
                    future.set_exception(exc)


async def complete_assessment(assessment_id: str, result: dict[str, Any], xp: int, rank: str) -> None:
    await _enqueue_general("complete_assessment", (json.dumps(result), xp, rank, assessment_id))


async def record_game_event(assessment_id: str, event_id: str, event_type: str, payload: dict[str, Any], xp_delta: int) -> bool:
    return bool(await _enqueue_general("game_event", (event_id, assessment_id, event_type, json.dumps(payload), xp_delta)))


async def record_analytics(anonymous_id: str, event_name: str, properties: dict[str, Any]) -> None:
    await _enqueue_general("analytics", (anonymous_id, event_name, json.dumps(properties)))


async def _enqueue_general(kind: str, params: tuple):
    if _general_queue is None:
        raise RuntimeError("Database write queue is not ready")
    future = asyncio.get_running_loop().create_future()
    await _general_queue.put((kind, params, future))
    return await future


async def _general_writer() -> None:
    statements = {
        "create_profile": """INSERT INTO user_profiles
            (session_id, token_hash, first_name, career_id, custom_career, career_stage, industry, region,
             education_level, years_experience, profile_json, created_at, updated_at, expires_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        "update_profile": """UPDATE user_profiles SET first_name=?, career_id=?, custom_career=?, career_stage=?, industry=?,
            region=?, education_level=?, years_experience=?, profile_json=?, updated_at=?, expires_at=?
            WHERE session_id=? AND token_hash=?""",
        "delete_profile": "DELETE FROM user_profiles WHERE session_id=? AND token_hash=?",
        "create_assessment": "INSERT INTO assessment_sessions(assessment_id, session_id, career_snapshot, question_ids, status) VALUES (?, ?, ?, ?, 'active')",
        "complete_assessment": "UPDATE assessment_sessions SET status='complete', result_json=?, xp=?, rank=?, updated_at=unixepoch() WHERE assessment_id=?",
        "analytics": "INSERT INTO analytics_events(anonymous_id, event_name, properties_json) VALUES (?, ?, ?)",
    }
    while True:
        first = await _general_queue.get()
        if first is None:
            return
        batch = [first]
        await asyncio.sleep(float(os.getenv("WRITE_BATCH_WINDOW_MS", "5")) / 1000)
        while len(batch) < 500:
            try:
                item = _general_queue.get_nowait()
            except asyncio.QueueEmpty:
                break
            if item is None:
                await _general_queue.put(None)
                break
            batch.append(item)
        completed = []
        try:
            async with write_connection() as db:
                await db.execute("BEGIN IMMEDIATE")
                for kind, params, future in batch:
                    if kind == "game_event":
                        cursor = await db.execute("INSERT OR IGNORE INTO game_events(event_id, assessment_id, event_type, payload_json, xp_delta) VALUES (?, ?, ?, ?, ?)", params)
                        created = cursor.rowcount == 1
                        if created:
                            await db.execute("UPDATE assessment_sessions SET xp=xp+?, updated_at=unixepoch() WHERE assessment_id=?", (params[4], params[1]))
                        completed.append((future, created))
                    else:
                        cursor = await db.execute(statements[kind], params)
                        completed.append((future, cursor.rowcount == 1))
                await db.commit()
            for future, result in completed:
                if not future.done():
                    future.set_result(result)
        except Exception as exc:
            for *_, future in batch:
                if not future.done():
                    future.set_exception(exc)


async def database_health() -> dict[str, Any]:
    started = time.perf_counter()
    try:
        async with connect() as db:
            row = await (await db.execute("SELECT 1 AS ok")).fetchone()
            mode = await (await db.execute("PRAGMA journal_mode")).fetchone()
        return {"ok": bool(row["ok"]), "latency_ms": round((time.perf_counter() - started) * 1000, 2), "engine": "sqlite", "journal_mode": mode[0]}
    except Exception:
        return {"ok": False, "latency_ms": round((time.perf_counter() - started) * 1000, 2), "engine": "sqlite"}


# ── Scan leads and email outbox ──────────────────────────────────────────────

async def record_scan_lead(lead: dict[str, Any]) -> int | None:
    """Store (or refresh) a scan result against an email address. Returns the lead id."""
    now = int(time.time())
    params = (
        lead.get("session_id"), lead.get("assessment_id"), lead["email"], lead.get("first_name"),
        lead.get("career_id"), lead.get("career_title"), lead.get("industry"), lead.get("region"),
        lead.get("career_stage"), lead.get("ai_exposure"), lead.get("augmentation_potential"),
        lead.get("transformation_pressure"), lead.get("overall_status"), lead.get("rank"), lead.get("xp"),
        json.dumps(lead.get("result") or {}), 1 if lead.get("marketing_consent") else 0,
        lead.get("consent_source"), now if lead.get("marketing_consent") else None, now,
    )
    async with write_connection() as db:
        await db.execute("BEGIN IMMEDIATE")
        await db.execute(
            """INSERT INTO scan_leads(session_id, assessment_id, email, first_name, career_id, career_title,
                industry, region, career_stage, ai_exposure, augmentation_potential, transformation_pressure,
                overall_status, rank, xp, result_json, marketing_consent, consent_source, consent_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(assessment_id, email) DO UPDATE SET
                ai_exposure=excluded.ai_exposure, augmentation_potential=excluded.augmentation_potential,
                transformation_pressure=excluded.transformation_pressure, overall_status=excluded.overall_status,
                rank=excluded.rank, xp=excluded.xp, result_json=excluded.result_json,
                marketing_consent=excluded.marketing_consent, consent_source=excluded.consent_source,
                consent_at=COALESCE(scan_leads.consent_at, excluded.consent_at), updated_at=excluded.updated_at""",
            params,
        )
        cursor = await db.execute(
            "SELECT id FROM scan_leads WHERE assessment_id IS ? AND email=?",
            (lead.get("assessment_id"), lead["email"]),
        )
        row = await cursor.fetchone()
        await db.commit()
    return int(row["id"]) if row else None


async def queue_email(lead_id: int | None, to_email: str, subject: str, html_body: str, text_body: str | None, kind: str = "results") -> int | None:
    async with write_connection() as db:
        cursor = await db.execute(
            "INSERT INTO email_outbox(lead_id, to_email, subject, html_body, text_body, kind) VALUES (?, ?, ?, ?, ?, ?)",
            (lead_id, to_email, subject, html_body, text_body, kind),
        )
        await db.commit()
        return cursor.lastrowid


async def claim_queued_emails(limit: int = 20) -> list[dict[str, Any]]:
    async with write_connection() as db:
        await db.execute("BEGIN IMMEDIATE")
        cursor = await db.execute(
            "SELECT * FROM email_outbox WHERE status='queued' ORDER BY created_at LIMIT ?", (limit,)
        )
        rows = [dict(row) for row in await cursor.fetchall()]
        for row in rows:
            await db.execute(
                "UPDATE email_outbox SET status='sending', attempts=attempts+1, updated_at=unixepoch() WHERE id=?",
                (row["id"],),
            )
        await db.commit()
    return rows


async def finish_email(email_id: int, status: str, provider_message_id: str | None = None, error: str | None = None) -> None:
    async with write_connection() as db:
        await db.execute(
            """UPDATE email_outbox SET status=?, provider_message_id=?, last_error=?, updated_at=unixepoch(),
                sent_at=CASE WHEN ?='sent' THEN unixepoch() ELSE sent_at END WHERE id=?""",
            (status, provider_message_id, error, status, email_id),
        )
        await db.commit()


async def requeue_stalled_emails(older_than_seconds: int = 300) -> int:
    cutoff = int(time.time()) - older_than_seconds
    async with write_connection() as db:
        cursor = await db.execute(
            "UPDATE email_outbox SET status='queued', updated_at=unixepoch() WHERE status='sending' AND updated_at < ?",
            (cutoff,),
        )
        await db.commit()
        return cursor.rowcount


async def list_scan_leads(consented_only: bool = True, since: int | None = None, limit: int = 100000) -> list[dict[str, Any]]:
    clauses, params = [], []
    if consented_only:
        clauses.append("marketing_consent=1")
    if since:
        clauses.append("created_at >= ?")
        params.append(since)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    params.append(limit)
    async with connect() as db:
        cursor = await db.execute(f"SELECT * FROM scan_leads {where} ORDER BY created_at DESC LIMIT ?", tuple(params))
        return [dict(row) for row in await cursor.fetchall()]


async def outbox_stats() -> dict[str, int]:
    async with connect() as db:
        cursor = await db.execute("SELECT status, COUNT(*) AS total FROM email_outbox GROUP BY status")
        return {row["status"]: row["total"] for row in await cursor.fetchall()}
