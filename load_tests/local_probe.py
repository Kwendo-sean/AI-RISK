"""Dependency-light progressive full-journey probe for local evidence.

This is intentionally not a substitute for the k6 staging test in scenario.js. It
provides reproducible local measurements when k6 is unavailable.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import statistics
import time
from collections import Counter

import httpx


class Recorder:
    def __init__(self):
        self.latencies: list[float] = []
        self.statuses: Counter[int] = Counter()

    def add(self, response: httpx.Response, elapsed: float):
        self.latencies.append(elapsed * 1000)
        self.statuses[response.status_code] += 1


def percentile(values: list[float], percentile_value: float) -> float:
    if not values:
        return 0.0
    values = sorted(values)
    index = min(len(values) - 1, math.ceil(percentile_value / 100 * len(values)) - 1)
    return values[index]


async def call(client: httpx.AsyncClient, recorder: Recorder, method: str, path: str, token: str | None = None, body=None):
    started = time.perf_counter()
    headers = {"X-Session-Token": token} if token else {}
    try:
        response = await client.request(method, path, headers=headers, json=body)
    except Exception:
        recorder.latencies.append((time.perf_counter() - started) * 1000)
        recorder.statuses[0] += 1
        return None
    recorder.add(response, time.perf_counter() - started)
    return response


async def journey(index: int, client: httpx.AsyncClient, recorder: Recorder):
    await call(client, recorder, "GET", "/")
    search = await call(client, recorder, "GET", "/api/v2/careers?q=mechanic&limit=8")
    if not search or search.status_code != 200:
        return
    profile = await call(client, recorder, "POST", "/api/v2/profiles", body={
        "first_name": "LoadUser", "career_id": "auto-mechanic", "custom_career": None,
        "career_stage": "Early-career", "industry": "Skilled Trades", "region": "Test region",
        "education_level": None, "years_experience": 3,
    })
    if not profile or profile.status_code != 201:
        return
    credentials = profile.json(); sid = credentials["session_id"]; token = credentials["access_token"]
    started = await call(client, recorder, "POST", f"/api/v2/profiles/{sid}/assessments", token, {})
    if not started or started.status_code != 201:
        return
    assessment = started.json(); aid = assessment["assessment_id"]
    while assessment.get("next_question"):
        question = assessment["next_question"]
        answer = await call(client, recorder, "POST", f"/api/v2/profiles/{sid}/assessments/{aid}/answers", token, {"question_id": question["id"], "answer_index": index % 5})
        if not answer or answer.status_code != 200:
            return
        assessment = answer.json()
    await call(client, recorder, "POST", f"/api/v2/profiles/{sid}/assessments/{aid}/complete", token, {})
    await call(client, recorder, "GET", f"/api/v2/profiles/{sid}/assessments/{aid}", token)
    await call(client, recorder, "POST", f"/api/v2/profiles/{sid}/assessments/{aid}/game-events", token, {"event_id": f"probe-{index}-{aid}"[:80], "event_type": "skill_opened", "payload": {"skill_id": "workflow_mapping"}})
    await call(client, recorder, "DELETE", f"/api/v2/profiles/{sid}", token)


async def run(base_url: str, concurrency: int):
    recorder = Recorder(); started = time.perf_counter()
    limits = httpx.Limits(max_connections=concurrency, max_keepalive_connections=min(concurrency, 200))
    timeout = httpx.Timeout(30.0, connect=10.0)
    async with httpx.AsyncClient(base_url=base_url, timeout=timeout, limits=limits) as client:
        await asyncio.gather(*(journey(index, client, recorder) for index in range(concurrency)))
    duration = time.perf_counter() - started
    failures = sum(count for status, count in recorder.statuses.items() if status == 0 or status >= 400)
    report = {
        "concurrent_journeys": concurrency,
        "requests": len(recorder.latencies),
        "duration_seconds": round(duration, 2),
        "requests_per_second": round(len(recorder.latencies) / duration, 2),
        "median_ms": round(statistics.median(recorder.latencies), 2) if recorder.latencies else 0,
        "p95_ms": round(percentile(recorder.latencies, 95), 2),
        "p99_ms": round(percentile(recorder.latencies, 99), 2),
        "error_rate": round(failures / max(1, len(recorder.latencies)), 5),
        "statuses": dict(sorted(recorder.statuses.items())),
    }
    print(json.dumps(report))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--concurrency", type=int, required=True)
    args = parser.parse_args()
    asyncio.run(run(args.base_url, args.concurrency))
