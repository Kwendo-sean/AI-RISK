"""Production-facing v2 API for profiles, assessments, results, and telemetry."""

from __future__ import annotations

import json
import hashlib
import logging
import os
import random
import re
import secrets
import time
import uuid
from collections import defaultdict, deque
from typing import Any, Literal

from fastapi import APIRouter, Header, HTTPException, Query, Request, Response
from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator
from starlette.middleware.base import BaseHTTPMiddleware

from assessment_engine import adapt_question_ids, questions_by_ids, score_assessment, select_question_ids
from platform_email import build_results_email, delivery_enabled
from platform_llm import health as llm_health, narrate_result
from platform_content import (
    DATASET_VERSION,
    fallback_career,
    get_career,
    load_careers,
    public_career_summary,
    search_careers,
    validate_content,
)
from platform_db import (
    complete_assessment,
    outbox_stats,
    queue_email,
    record_scan_lead,
    create_assessment,
    create_profile,
    database_health,
    delete_profile,
    get_assessment,
    get_latest_assessment,
    get_profile,
    hash_token,
    record_analytics,
    record_game_event,
    save_answer,
    update_profile,
)

logger = logging.getLogger("career_platform")
router = APIRouter(prefix="/api/v2", tags=["career-platform"])

CAREER_STAGES = {
    "Student", "Entry-level", "Early-career", "Mid-career", "Senior",
    "Manager or executive", "Founder or self-employed", "Career changer",
    "Currently unemployed or exploring",
}
ANALYTICS_EVENTS = {
    "onboarding_started", "onboarding_completed", "career_searched", "career_not_found",
    "assessment_started", "question_abandoned", "assessment_completed", "result_viewed",
    "skill_card_opened", "action_plan_started", "results_emailed", "error",
}
GAME_XP = {
    "scan_completed": 100,
    "threat_braced": 80,
    "skill_owned": 30,
    "skill_gap": 15,
    "skill_opened": 20,
    "action_started": 120,
}
_auth_cache: dict[str, tuple[str, dict[str, Any], float]] = {}


def _clean_text(value: str | None, maximum: int) -> str | None:
    if value is None:
        return None
    value = re.sub(r"\s+", " ", value).strip()
    if not value:
        return None
    if any(ord(ch) < 32 for ch in value):
        raise ValueError("contains unsupported control characters")
    return value[:maximum]


class ProfileInput(BaseModel):
    first_name: str = Field(min_length=1, max_length=50)
    career_id: str | None = Field(default=None, max_length=80)
    custom_career: str | None = Field(default=None, max_length=160)
    career_stage: str
    industry: str = Field(min_length=1, max_length=100)
    region: str | None = Field(default=None, max_length=100)
    education_level: str | None = Field(default=None, max_length=100)
    years_experience: int | None = Field(default=None, ge=0, le=70)

    @field_validator("first_name")
    @classmethod
    def valid_name(cls, value: str) -> str:
        cleaned = _clean_text(value, 50)
        if not cleaned or not re.search(r"[^\W\d_]", cleaned, re.UNICODE):
            raise ValueError("Enter a valid first name")
        return cleaned

    @field_validator("career_stage")
    @classmethod
    def valid_stage(cls, value: str) -> str:
        if value not in CAREER_STAGES:
            raise ValueError("Choose a supported career stage")
        return value

    @field_validator("career_id", "custom_career", "industry", "region", "education_level")
    @classmethod
    def clean_fields(cls, value: str | None) -> str | None:
        return _clean_text(value, 160)

    @model_validator(mode="after")
    def career_present(self) -> "ProfileInput":
        if not self.career_id and not self.custom_career:
            raise ValueError("Choose a career or describe your role")
        if self.career_id and self.career_id != "custom-role" and not get_career(self.career_id):
            raise ValueError("Selected career was not found")
        return self


class AnswerInput(BaseModel):
    question_id: str = Field(min_length=3, max_length=100)
    answer_index: int = Field(ge=0, le=6)


class GameEventInput(BaseModel):
    event_id: str = Field(min_length=8, max_length=80)
    event_type: Literal["scan_completed", "threat_braced", "skill_owned", "skill_gap", "skill_opened", "action_started"]
    payload: dict[str, Any] = Field(default_factory=dict)


class ResultsEmailInput(BaseModel):
    email: EmailStr
    marketing_consent: bool = False


class AnalyticsInput(BaseModel):
    anonymous_id: str = Field(min_length=8, max_length=80)
    event_name: str = Field(min_length=2, max_length=50)
    properties: dict[str, Any] = Field(default_factory=dict)


async def _authorized_profile(session_id: str, token: str | None) -> dict[str, Any]:
    if not token:
        raise HTTPException(401, "Session token required")
    cached = _auth_cache.get(session_id)
    token_digest = hash_token(token)
    if cached and cached[2] > time.monotonic() and secrets.compare_digest(cached[0], token_digest):
        return cached[1]
    profile = await get_profile(session_id, token)
    if not profile:
        raise HTTPException(401, "Session is invalid or expired")
    if len(_auth_cache) > 10000:
        now = time.monotonic()
        for key in list(_auth_cache)[:1000]:
            if _auth_cache[key][2] <= now:
                _auth_cache.pop(key, None)
    _auth_cache[session_id] = (token_digest, profile, time.monotonic() + 30)
    return profile


def _profile_public(row: dict[str, Any]) -> dict[str, Any]:
    return json.loads(row["profile_json"])


def _assessment_public(assessment: dict[str, Any], include_questions: bool = False) -> dict[str, Any]:
    question_ids = assessment["question_ids"]
    answers = assessment["answers"]
    questions = questions_by_ids(question_ids)
    unanswered = [q for q in questions if q["id"] not in answers]
    payload = {
        "assessment_id": assessment["assessment_id"],
        "status": assessment["status"],
        "career": public_career_summary(assessment["career"]),
        "answers": answers,
        "next_question": unanswered[0] if unanswered else None,
        "progress": {"answered": len(answers), "total": len(question_ids), "percent": round(len(answers) / max(1, len(question_ids)) * 100)},
        "xp": assessment["xp"],
        "rank": assessment["rank"],
        "result": assessment["result"],
    }
    if include_questions:
        payload["questions"] = questions
    return payload


@router.get("/meta")
async def meta() -> dict[str, Any]:
    validation = validate_content()
    return {
        "dataset_version": DATASET_VERSION,
        "career_count": len(load_careers()),
        "industries": sorted({career["industry"] for career in load_careers()}),
        "career_stages": sorted(CAREER_STAGES),
        "content_valid": validation["valid"],
    }


@router.get("/careers")
async def careers(q: str = Query("", max_length=100), industry: str | None = Query(None, max_length=100), limit: int = Query(30, ge=1, le=100)) -> dict[str, Any]:
    matches = search_careers(q, industry, limit)
    return {"total": len(matches), "careers": [public_career_summary(career) for career in matches], "query": q}


@router.get("/careers/{career_id}")
async def career_detail(career_id: str) -> dict[str, Any]:
    career = get_career(career_id)
    if not career:
        raise HTTPException(404, "Career not found")
    return career


@router.get("/content/coverage")
async def content_coverage() -> dict[str, Any]:
    return validate_content()


@router.post("/profiles", status_code=201)
async def profile_create(body: ProfileInput) -> dict[str, Any]:
    profile = body.model_dump()
    credentials = await create_profile(profile)
    return {**credentials, "profile": profile, "privacy": "Stored for 90 days by default. Your name is not included in analytics and can be deleted at any time."}


@router.get("/profiles/{session_id}")
async def profile_read(session_id: str, x_session_token: str | None = Header(None)) -> dict[str, Any]:
    row = await _authorized_profile(session_id, x_session_token)
    assessment = await get_latest_assessment(session_id)
    return {"profile": _profile_public(row), "assessment": _assessment_public(assessment) if assessment else None}


@router.put("/profiles/{session_id}")
async def profile_update(session_id: str, body: ProfileInput, x_session_token: str | None = Header(None)) -> dict[str, Any]:
    await _authorized_profile(session_id, x_session_token)
    changed = await update_profile(session_id, x_session_token or "", body.model_dump())
    if not changed:
        raise HTTPException(409, "Profile could not be updated")
    _auth_cache.pop(session_id, None)
    return {"status": "updated", "profile": body.model_dump()}


@router.delete("/profiles/{session_id}", status_code=204)
async def profile_delete(session_id: str, x_session_token: str | None = Header(None)) -> Response:
    await _authorized_profile(session_id, x_session_token)
    await delete_profile(session_id, x_session_token or "")
    _auth_cache.pop(session_id, None)
    return Response(status_code=204)


@router.post("/profiles/{session_id}/assessments", status_code=201)
async def assessment_start(session_id: str, x_session_token: str | None = Header(None)) -> dict[str, Any]:
    row = await _authorized_profile(session_id, x_session_token)
    profile = _profile_public(row)
    career = get_career(profile.get("career_id") or "")
    if not career:
        career = fallback_career(profile.get("custom_career") or "Unlisted role", profile.get("industry") or "Other")
    question_ids = select_question_ids(career, profile)
    assessment_id = await create_assessment(session_id, career, question_ids)
    assessment = await get_assessment(assessment_id, session_id)
    return _assessment_public(assessment)


@router.get("/profiles/{session_id}/assessments/{assessment_id}")
async def assessment_read(session_id: str, assessment_id: str, x_session_token: str | None = Header(None)) -> dict[str, Any]:
    await _authorized_profile(session_id, x_session_token)
    assessment = await get_assessment(assessment_id, session_id)
    if not assessment:
        raise HTTPException(404, "Assessment not found")
    return _assessment_public(assessment)


@router.post("/profiles/{session_id}/assessments/{assessment_id}/answers")
async def assessment_answer(session_id: str, assessment_id: str, body: AnswerInput, x_session_token: str | None = Header(None)) -> dict[str, Any]:
    await _authorized_profile(session_id, x_session_token)
    assessment = await get_assessment(assessment_id, session_id)
    if not assessment:
        raise HTTPException(404, "Assessment not found")
    if assessment["status"] == "complete":
        raise HTTPException(409, "Assessment is already complete")
    questions = {q["id"]: q for q in questions_by_ids(assessment["question_ids"])}
    if body.question_id not in questions:
        raise HTTPException(400, "Question is not part of this assessment")
    if body.answer_index >= len(questions[body.question_id]["answers"]):
        raise HTTPException(422, "Answer is outside the allowed range")
    updated_answers = {**assessment["answers"], body.question_id: body.answer_index}
    question_ids = adapt_question_ids(assessment["question_ids"], updated_answers)
    await save_answer(assessment_id, body.question_id, body.answer_index, question_ids)
    assessment["answers"] = updated_answers
    assessment["question_ids"] = question_ids
    return _assessment_public(assessment)


@router.post("/profiles/{session_id}/assessments/{assessment_id}/complete")
async def assessment_finish(session_id: str, assessment_id: str, x_session_token: str | None = Header(None)) -> dict[str, Any]:
    profile = _profile_public(await _authorized_profile(session_id, x_session_token))
    assessment = await get_assessment(assessment_id, session_id)
    if not assessment:
        raise HTTPException(404, "Assessment not found")
    if assessment["status"] == "complete":
        return _assessment_public(assessment)
    missing = [qid for qid in assessment["question_ids"] if qid not in assessment["answers"]]
    if missing:
        raise HTTPException(409, f"Answer all assessment questions before completion ({len(missing)} remaining)")
    result = score_assessment(assessment["career"], assessment["question_ids"], assessment["answers"])
    narration = await narrate_result(
        assessment["career"].get("canonical_title", ""), profile.get("career_stage", ""), profile.get("region", ""), result
    )
    if narration:
        result["personal_note"] = narration
    xp = 100 + len(assessment["answers"]) * 20
    rank = "Pathfinder" if xp >= 400 else "Scout"
    await complete_assessment(assessment_id, result, xp, rank)
    assessment.update({"status": "complete", "result": result, "xp": xp, "rank": rank})
    return _assessment_public(assessment)


@router.post("/profiles/{session_id}/assessments/{assessment_id}/game-events")
async def game_event(session_id: str, assessment_id: str, body: GameEventInput, x_session_token: str | None = Header(None)) -> dict[str, Any]:
    await _authorized_profile(session_id, x_session_token)
    assessment = await get_assessment(assessment_id, session_id)
    if not assessment:
        raise HTTPException(404, "Assessment not found")
    xp_delta = GAME_XP[body.event_type]
    created = await record_game_event(assessment_id, body.event_id, body.event_type, {k: v for k, v in body.payload.items() if k in {"skill_id", "construct_id"}}, xp_delta)
    return {"awarded": created, "xp_delta": xp_delta if created else 0, "xp": assessment["xp"] + (xp_delta if created else 0)}


@router.post("/profiles/{session_id}/assessments/{assessment_id}/email", status_code=202)
async def email_results(session_id: str, assessment_id: str, body: ResultsEmailInput, x_session_token: str | None = Header(None)) -> dict[str, Any]:
    """Store the scan against an email address and queue the results email."""
    row = await _authorized_profile(session_id, x_session_token)
    profile = _profile_public(row)
    assessment = await get_assessment(assessment_id, session_id)
    if not assessment:
        raise HTTPException(404, "Assessment not found")
    if assessment["status"] != "complete" or not assessment["result"]:
        raise HTTPException(409, "Finish the assessment before requesting results by email")

    result = assessment["result"]
    career = assessment["career"]
    lead_id = await record_scan_lead({
        "session_id": session_id,
        "assessment_id": assessment_id,
        "email": str(body.email).lower(),
        "first_name": profile.get("first_name"),
        "career_id": career.get("id"),
        "career_title": career.get("canonical_title"),
        "industry": profile.get("industry"),
        "region": profile.get("region"),
        "career_stage": profile.get("career_stage"),
        "ai_exposure": career.get("ai_exposure"),
        "augmentation_potential": career.get("ai_augmentation_potential"),
        "transformation_pressure": result.get("overall", {}).get("transformation_pressure"),
        "overall_status": result.get("overall", {}).get("status"),
        "rank": assessment["rank"],
        "xp": assessment["xp"],
        "result": result,
        "marketing_consent": body.marketing_consent,
        "consent_source": "results_screen",
    })
    subject, html_body, text_body = build_results_email(
        profile.get("first_name") or "", career.get("canonical_title") or "your role", result, assessment["xp"], assessment["rank"]
    )
    await queue_email(lead_id, str(body.email).lower(), subject, html_body, text_body)
    return {"queued": True, "delivery_enabled": delivery_enabled()}


@router.post("/analytics", status_code=202)
async def analytics(body: AnalyticsInput) -> dict[str, str]:
    if body.event_name not in ANALYTICS_EVENTS:
        raise HTTPException(422, "Unsupported analytics event")
    safe_properties = {k: v for k, v in body.properties.items() if k in {"screen", "career_id", "industry", "question_id", "skill_id", "error_code", "query_length"}}
    await record_analytics(body.anonymous_id, body.event_name, safe_properties)
    return {"status": "accepted"}


@router.get("/ready")
async def ready(response: Response) -> dict[str, Any]:
    db = await database_health()
    content = validate_content()
    ready_state = db["ok"] and content["valid"]
    if not ready_state:
        response.status_code = 503
    return {
        "status": "ready" if ready_state else "not_ready",
        "database": db,
        "content": {"valid": content["valid"], "errors": len(content["errors"]), "warnings": len(content["warnings"])},
        "email": {"delivery_enabled": delivery_enabled(), "outbox": await outbox_stats()},
        "local_model": await llm_health(),
    }


class SecurityAndOperationsMiddleware(BaseHTTPMiddleware):
    """Request IDs, conservative headers, body limits, lightweight local rate limits, and timings."""

    buckets: dict[str, deque[float]] = defaultdict(deque)
    _last_prune: float = 0.0

    @classmethod
    def _over_limit(cls, identity: str, now: float, limit: int) -> bool:
        bucket = cls.buckets[identity]
        while bucket and bucket[0] < now - 60:
            bucket.popleft()
        if len(bucket) >= limit:
            return True
        bucket.append(now)
        return False

    @classmethod
    def _prune(cls, now: float) -> None:
        """Drop idle buckets so a long-running process does not grow a map of every visitor."""
        if now - cls._last_prune < 60:
            return
        cls._last_prune = now
        for identity in [k for k, v in cls.buckets.items() if not v or v[-1] < now - 120]:
            cls.buckets.pop(identity, None)

    async def dispatch(self, request: Request, call_next):
        started = time.perf_counter()
        request_id = request.headers.get("x-request-id", str(uuid.uuid4()))[:80]
        max_body = int(os.getenv("MAX_REQUEST_BYTES", "65536"))
        try:
            content_length = int(request.headers.get("content-length", "0"))
        except ValueError:
            content_length = max_body + 1
        if content_length > max_body:
            return Response("Request too large", status_code=413)

        if request.url.path.startswith("/api/"):
            now = time.monotonic()
            address = request.client.host if request.client else "unknown"
            # Key on the session token where we have one. Mobile carriers and offices put
            # hundreds of real users behind a single egress IP, so an IP-only bucket
            # throttles a whole network the moment a few people scan at once.
            token = request.headers.get("x-session-token")
            self._prune(now)
            if token:
                identity = f"s:{hashlib.sha256(token.encode()).hexdigest()[:32]}"
                limited = self._over_limit(identity, now, int(os.getenv("RATE_LIMIT_PER_MINUTE", "240")))
            elif request.method == "POST" and request.url.path.rstrip("/").endswith("/profiles"):
                # Creating a profile is the one unauthenticated write, so it gets its own
                # ceiling. Raise RATE_LIMIT_SIGNUP_PER_MINUTE if your audience shares an
                # egress IP (carrier NAT, a campus, an office) and legitimately trips it.
                limited = self._over_limit(f"n:{address}", now, int(os.getenv("RATE_LIMIT_SIGNUP_PER_MINUTE", "120")))
            else:
                limited = False
            # A high per-IP ceiling still bounds one genuinely abusive source.
            if not limited:
                limited = self._over_limit(f"i:{address}", now, int(os.getenv("RATE_LIMIT_IP_PER_MINUTE", "3000")))
            if limited:
                response = Response("Rate limit exceeded", status_code=429, headers={"Retry-After": "60"})
            else:
                response = await call_next(request)
        else:
            response = await call_next(request)

        duration_ms = (time.perf_counter() - started) * 1000
        response.headers["X-Request-ID"] = request_id
        response.headers["Server-Timing"] = f"app;dur={duration_ms:.1f}"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(self), microphone=(), geolocation=()"
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self'; "
            "img-src 'self' data: blob:; connect-src 'self'; font-src 'self'; object-src 'none'; "
            "base-uri 'self'; frame-ancestors 'none'; form-action 'self'"
        )
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        elif request.url.path.endswith((".css", ".js", ".svg", ".woff2")):
            response.headers["Cache-Control"] = "public, max-age=3600"
        sample_rate = float(os.getenv("REQUEST_LOG_SAMPLE", "0.01"))
        slow_ms = float(os.getenv("LOG_SLOW_REQUEST_MS", "2000"))
        log_payload = {"event": "request", "request_id": request_id, "method": request.method,
                       "route": request.scope.get("route").path if request.scope.get("route") else "unmatched",
                       "status": response.status_code, "duration_ms": round(duration_ms, 1)}
        if response.status_code >= 500:
            logger.error(json.dumps(log_payload))
        elif duration_ms >= slow_ms or random.random() < sample_rate:
            logger.info(json.dumps(log_payload))
        return response
