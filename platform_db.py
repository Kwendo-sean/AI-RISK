"""Database facade: picks a backend and forwards every repository call to it.

    DATABASE_URL=postgresql://...   -> db_postgres  (production, many replicas)
    unset, or sqlite:///path        -> db_sqlite    (local dev, offline single node)

The API layer imports from this module only, so switching stores is an environment
change rather than a code change.
"""

from __future__ import annotations

import hashlib
import os
from typing import Any

import db_sqlite

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
DB_PATH = os.getenv("DB_PATH", "willaijob.db")

_backend = db_sqlite


def backend_name() -> str:
    return "postgres" if _backend is not db_sqlite else "sqlite"


def _select_backend():
    """Choose the backend from DATABASE_URL, importing asyncpg only when needed."""
    global _backend
    url = DATABASE_URL or os.getenv("DATABASE_URL", "").strip()
    if url and url.startswith(("postgres://", "postgresql://")):
        import db_postgres

        db_postgres.set_dsn(url)
        _backend = db_postgres
        return
    if url.startswith("sqlite:///"):
        db_sqlite.set_db_path(url[len("sqlite:///"):])
    else:
        db_sqlite.set_db_path(DB_PATH)
    _backend = db_sqlite


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


async def init_platform_db() -> None:
    _select_backend()
    await _backend.init_platform_db()


async def close_platform_db() -> None:
    await _backend.close_platform_db()


async def create_profile(profile: dict[str, Any]) -> dict[str, str]:
    return await _backend.create_profile(profile)


async def get_profile(session_id: str, token: str) -> dict[str, Any] | None:
    return await _backend.get_profile(session_id, token)


async def update_profile(session_id: str, token: str, profile: dict[str, Any]) -> bool:
    return await _backend.update_profile(session_id, token, profile)


async def delete_profile(session_id: str, token: str) -> bool:
    return await _backend.delete_profile(session_id, token)


async def create_assessment(session_id: str, career: dict[str, Any], question_ids: list[str]) -> str:
    return await _backend.create_assessment(session_id, career, question_ids)


async def get_assessment(assessment_id: str, session_id: str) -> dict[str, Any] | None:
    return await _backend.get_assessment(assessment_id, session_id)


async def get_latest_assessment(session_id: str) -> dict[str, Any] | None:
    return await _backend.get_latest_assessment(session_id)


async def save_answer(assessment_id: str, question_id: str, answer_index: int, question_ids: list[str]) -> None:
    await _backend.save_answer(assessment_id, question_id, answer_index, question_ids)


async def complete_assessment(assessment_id: str, result: dict[str, Any], xp: int, rank: str) -> None:
    await _backend.complete_assessment(assessment_id, result, xp, rank)


async def record_game_event(assessment_id: str, event_id: str, event_type: str, payload: dict[str, Any], xp_delta: int) -> bool:
    return await _backend.record_game_event(assessment_id, event_id, event_type, payload, xp_delta)


async def record_analytics(anonymous_id: str, event_name: str, properties: dict[str, Any]) -> None:
    await _backend.record_analytics(anonymous_id, event_name, properties)


async def record_scan_lead(lead: dict[str, Any]) -> int | None:
    return await _backend.record_scan_lead(lead)


async def queue_email(lead_id: int | None, to_email: str, subject: str, html_body: str, text_body: str | None, kind: str = "results") -> int | None:
    return await _backend.queue_email(lead_id, to_email, subject, html_body, text_body, kind)


async def claim_queued_emails(limit: int = 20) -> list[dict[str, Any]]:
    return await _backend.claim_queued_emails(limit)


async def finish_email(email_id: int, status: str, provider_message_id: str | None = None, error: str | None = None) -> None:
    await _backend.finish_email(email_id, status, provider_message_id, error)


async def requeue_stalled_emails(older_than_seconds: int = 300) -> int:
    return await _backend.requeue_stalled_emails(older_than_seconds)


async def list_scan_leads(consented_only: bool = True, since: int | None = None, limit: int = 100000) -> list[dict[str, Any]]:
    return await _backend.list_scan_leads(consented_only, since, limit)


async def outbox_stats() -> dict[str, int]:
    return await _backend.outbox_stats()


async def database_health() -> dict[str, Any]:
    return await _backend.database_health()
