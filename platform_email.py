"""Results emails: compose, queue, and deliver through Resend.

Every email is written to the email_outbox table first and sent by a background
flusher. That ordering matters for two reasons:

  * a send failure (or a deployment with no internet, such as the offline Raspberry
    Pi) never loses the message - it stays queued until the next flush succeeds;
  * the HTTP request that finishes an assessment returns immediately instead of
    waiting on a third-party API.

Set RESEND_API_KEY and EMAIL_FROM to enable delivery. With no key the app still
records leads and queues mail, it just never sends - which is exactly what an
air-gapped deployment wants.
"""

from __future__ import annotations

import asyncio
import html
import logging
import os
from typing import Any

import httpx

import platform_db

logger = logging.getLogger("career_platform.email")

RESEND_API_URL = "https://api.resend.com/emails"
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "").strip()
EMAIL_FROM = os.getenv("EMAIL_FROM", "Future Skills <onboarding@resend.dev>").strip()
EMAIL_REPLY_TO = os.getenv("EMAIL_REPLY_TO", "").strip()
PUBLIC_URL = os.getenv("PUBLIC_URL", "").strip()
FLUSH_INTERVAL = float(os.getenv("EMAIL_FLUSH_SECONDS", "15"))
FLUSH_BATCH = int(os.getenv("EMAIL_FLUSH_BATCH", "20"))
MAX_ATTEMPTS = int(os.getenv("EMAIL_MAX_ATTEMPTS", "5"))
SEND_TIMEOUT = float(os.getenv("EMAIL_SEND_TIMEOUT", "10"))

_flusher: asyncio.Task | None = None

DIMENSION_LABELS = {
    "automation_exposure": "How much of your work AI can already do",
    "augmentation_opportunity": "How much AI could speed you up",
    "human_advantage": "Work that still needs a person",
    "physical_defensibility": "Hands-on work in the real world",
    "accountability_protection": "Decisions someone must answer for",
    "reskilling_urgency": "How soon to start learning",
    "career_adaptability": "How easily you can adapt",
}


def delivery_enabled() -> bool:
    return bool(RESEND_API_KEY)


def _esc(value: Any) -> str:
    return html.escape(str(value if value is not None else ""))


def build_results_email(first_name: str, career_title: str, result: dict[str, Any], xp: int, rank: str) -> tuple[str, str, str]:
    """Return (subject, html_body, text_body) for a finished scan."""
    dimensions = result.get("dimensions", {})
    overall = result.get("overall", {})
    skills = result.get("skill_recommendations", [])[:3]
    status = overall.get("status", "your job is changing")
    name = _esc(first_name or "there")

    rows = "".join(
        f'<tr><td style="padding:8px 0;color:#4b4b52;font-size:14px">{_esc(DIMENSION_LABELS.get(key, key))}</td>'
        f'<td style="padding:8px 0;text-align:right;font-weight:700;font-size:14px">{int(value)}/100</td></tr>'
        for key, value in dimensions.items()
    )
    steps = "".join(
        f'<li style="margin-bottom:14px"><strong>{_esc(skill.get("name"))}</strong>'
        f'<div style="color:#4b4b52;font-size:14px;margin-top:4px">{_esc(skill.get("why"))}</div>'
        f'<div style="font-size:13px;margin-top:6px"><em>Start here:</em> {_esc(skill.get("first_action"))}</div></li>'
        for skill in skills
    )
    link = (
        f'<p style="font-size:14px"><a href="{_esc(PUBLIC_URL)}" style="color:#c0271f">Run the scan again</a>'
        " whenever your work changes.</p>"
        if PUBLIC_URL
        else ""
    )

    subject = f"{first_name or 'Your'} career scan: {status}"
    body = f"""<!doctype html>
<html><body style="margin:0;padding:24px;background:#f4f1ec;font-family:-apple-system,Segoe UI,Roboto,sans-serif;color:#14141a">
  <div style="max-width:560px;margin:0 auto;background:#fff;padding:32px;border:1px solid #e2ddd5">
    <p style="margin:0 0 6px;font-size:11px;letter-spacing:.12em;text-transform:uppercase;color:#c0271f">Your career scan</p>
    <h1 style="margin:0 0 16px;font-size:26px;line-height:1.2">{name}, here is where you stand</h1>
    <p style="font-size:15px;line-height:1.6;color:#3b3b42">
      As a {_esc(career_title)}, {_esc(status)}. Hand the repetitive parts to AI and spend more of your
      time where your judgement counts.
    </p>
    <h2 style="font-size:15px;margin:26px 0 8px">Your seven scores</h2>
    <table style="width:100%;border-collapse:collapse;border-top:1px solid #e2ddd5">{rows}</table>
    <h2 style="font-size:15px;margin:26px 0 8px">What to learn next</h2>
    <ol style="padding-left:18px;margin:0">{steps}</ol>
    <p style="font-size:14px;margin-top:24px">You finished with <strong>{int(xp)} XP</strong> at rank <strong>{_esc(rank)}</strong>.</p>
    {link}
    <p style="margin-top:28px;font-size:12px;color:#84807a;border-top:1px solid #e2ddd5;padding-top:14px">
      You are getting this because you asked for your results by email. Reply to this message to be removed.
    </p>
  </div>
</body></html>"""

    text = (
        f"{first_name or 'Hi'}, here is where you stand.\n\n"
        f"As a {career_title}, {status}.\n\n"
        + "\n".join(f"- {DIMENSION_LABELS.get(k, k)}: {int(v)}/100" for k, v in dimensions.items())
        + "\n\nWhat to learn next:\n"
        + "\n".join(f"- {s.get('name')}: {s.get('first_action')}" for s in skills)
        + f"\n\nYou finished with {int(xp)} XP at rank {rank}.\n"
    )
    return subject, body, text


async def send_via_resend(client: httpx.AsyncClient, to_email: str, subject: str, html_body: str, text_body: str | None) -> str:
    payload: dict[str, Any] = {
        "from": EMAIL_FROM,
        "to": [to_email],
        "subject": subject,
        "html": html_body,
    }
    if text_body:
        payload["text"] = text_body
    if EMAIL_REPLY_TO:
        payload["reply_to"] = EMAIL_REPLY_TO
    response = await client.post(
        RESEND_API_URL,
        json=payload,
        headers={"Authorization": f"Bearer {RESEND_API_KEY}"},
        timeout=SEND_TIMEOUT,
    )
    response.raise_for_status()
    return str(response.json().get("id", ""))


async def flush_once(limit: int = FLUSH_BATCH) -> dict[str, int]:
    """Send one batch. Safe to call from a script or the background task."""
    if not delivery_enabled():
        return {"sent": 0, "failed": 0, "skipped": 0}
    await platform_db.requeue_stalled_emails()
    batch = await platform_db.claim_queued_emails(limit)
    if not batch:
        return {"sent": 0, "failed": 0, "skipped": 0}
    counts = {"sent": 0, "failed": 0, "skipped": 0}
    async with httpx.AsyncClient() as client:
        for row in batch:
            try:
                message_id = await send_via_resend(
                    client, row["to_email"], row["subject"], row["html_body"], row.get("text_body")
                )
                await platform_db.finish_email(row["id"], "sent", provider_message_id=message_id)
                counts["sent"] += 1
            except Exception as error:  # noqa: BLE001 - record and move on
                permanent = int(row.get("attempts") or 0) >= MAX_ATTEMPTS
                status = "failed" if permanent else "queued"
                await platform_db.finish_email(row["id"], status, error=str(error)[:500])
                counts["failed" if permanent else "skipped"] += 1
                logger.warning("email %s %s: %s", row["id"], status, str(error)[:200])
    return counts


async def _flush_loop() -> None:
    while True:
        try:
            await asyncio.sleep(FLUSH_INTERVAL)
            await flush_once()
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 - a broken batch must not kill the loop
            logger.exception("email flush failed")


def start_email_worker() -> None:
    global _flusher
    if not delivery_enabled():
        logger.info("RESEND_API_KEY not set - results emails will be queued but not sent")
        return
    if _flusher is None or _flusher.done():
        _flusher = asyncio.create_task(_flush_loop(), name="email-flusher")


async def stop_email_worker() -> None:
    global _flusher
    if _flusher is not None:
        _flusher.cancel()
        try:
            await _flusher
        except (asyncio.CancelledError, Exception):  # noqa: BLE001
            pass
        _flusher = None
