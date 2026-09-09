"""Optional local-model narration. Supports llama.cpp (llama-server) and Ollama.

What the model is and is not used for
-------------------------------------
NOT used for scoring. The seven dimensions, the exposure percentile and the skill
selection are computed in assessment_engine.py from the user's answers and the
research datasets. That has to stay deterministic: the same answers must always
produce the same numbers, results must be explainable, and a 1B model on a Pi is
neither a calculator nor a reliable ranker.

IS used for phrasing. The model rewrites the already-computed result into one or
two sentences addressed to this person's job and situation. If the model is slow,
absent, busy, or produces something malformed, the deterministic sentence is used
instead and nothing downstream notices.

Backends
--------
    LLM_BACKEND=llamacpp   LLM_URL=http://127.0.0.1:8081     # llama-server, OpenAI-compatible
    LLM_BACKEND=ollama     LLM_URL=http://127.0.0.1:11434

`OLLAMA_URL` is still honoured for backwards compatibility.

Booth safety
------------
One shared model server, and at most LLM_MAX_CONCURRENCY requests in flight (default 2
- a Pi 5 doing CPU inference will thrash above that). Anything over the limit skips
narration rather than queueing behind a slow generation, so a busy booth degrades into
the static copy instead of into a hang.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

import httpx

logger = logging.getLogger("career_platform.llm")

LLM_URL = (os.getenv("LLM_URL") or os.getenv("OLLAMA_URL") or "").strip().rstrip("/")
LLM_BACKEND = (os.getenv("LLM_BACKEND") or ("ollama" if os.getenv("OLLAMA_URL") else "llamacpp")).strip().lower()
LLM_MODEL = (os.getenv("LLM_MODEL") or os.getenv("OLLAMA_MODEL") or "gemma3:1b").strip()
TIMEOUT = float(os.getenv("LLM_TIMEOUT", os.getenv("OLLAMA_TIMEOUT", "8")))
MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", os.getenv("OLLAMA_MAX_TOKENS", "120")))
MAX_CONCURRENCY = int(os.getenv("LLM_MAX_CONCURRENCY", "2"))

_gate = asyncio.Semaphore(MAX_CONCURRENCY)

PROMPT = """You are helping someone understand a career assessment that has already been calculated.
Do not invent numbers, do not contradict the figures, and do not predict that their job will disappear.

Job: {career}
Where they are: {stage}, {region}
Result: {status}
Scores out of 100: {scores}
First recommended skill: {skill}

Write two plain sentences, addressed to them as "you", that say what this means for their
week-to-week work and what to do first. No greeting, no sign-off, no bullet points, no headings."""


def enabled() -> bool:
    return bool(LLM_URL)


def _build_prompt(career: str, stage: str, region: str, result: dict[str, Any]) -> str:
    dimensions = result.get("dimensions", {})
    skills = result.get("skill_recommendations") or [{}]
    return PROMPT.format(
        career=career or "their role",
        stage=stage or "mid-career",
        region=region or "their market",
        status=result.get("overall", {}).get("status", "their job is changing"),
        scores=", ".join(f"{key.replace('_', ' ')} {int(value)}" for key, value in dimensions.items()),
        skill=skills[0].get("name", "verifying AI output"),
    )


async def _call_llamacpp(client: httpx.AsyncClient, prompt: str) -> str:
    """llama-server's OpenAI-compatible endpoint. Works with any llama.cpp build."""
    response = await client.post(
        f"{LLM_URL}/v1/chat/completions",
        json={
            "model": LLM_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.4,
            "max_tokens": MAX_TOKENS,
            "stream": False,
        },
    )
    response.raise_for_status()
    payload = response.json()
    return (payload.get("choices") or [{}])[0].get("message", {}).get("content", "")


async def _call_ollama(client: httpx.AsyncClient, prompt: str) -> str:
    response = await client.post(
        f"{LLM_URL}/api/generate",
        json={
            "model": LLM_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.4, "num_predict": MAX_TOKENS},
        },
    )
    response.raise_for_status()
    return response.json().get("response") or ""


async def narrate_result(career: str, stage: str, region: str, result: dict[str, Any]) -> str | None:
    """Return a personalised sentence pair, or None to fall back to the static copy."""
    if not enabled():
        return None
    if _gate.locked() and _gate._value <= 0:  # noqa: SLF001 - cheap check, avoids queueing
        logger.debug("local model busy, using static copy")
        return None

    prompt = _build_prompt(career, stage, region, result)
    try:
        async with _gate:
            async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                caller = _call_ollama if LLM_BACKEND == "ollama" else _call_llamacpp
                text = " ".join((await caller(client, prompt)).split())
    except Exception as error:  # noqa: BLE001 - never let narration break a result
        logger.debug("local model narration unavailable: %s", error)
        return None

    # Guard against a small model rambling, refusing, or emitting markdown.
    if not text or len(text) < 40 or len(text) > 600 or text.startswith(("#", "-", "*")):
        return None
    return text


async def health() -> dict[str, Any]:
    if not enabled():
        return {"enabled": False}
    probe = "/api/tags" if LLM_BACKEND == "ollama" else "/health"
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.get(f"{LLM_URL}{probe}")
            response.raise_for_status()
        return {
            "enabled": True,
            "reachable": True,
            "backend": LLM_BACKEND,
            "model": LLM_MODEL,
            "in_flight": MAX_CONCURRENCY - _gate._value,  # noqa: SLF001
            "max_concurrency": MAX_CONCURRENCY,
        }
    except Exception as error:  # noqa: BLE001
        return {"enabled": True, "reachable": False, "backend": LLM_BACKEND, "error": str(error)[:120]}
