"""Pre-flight check for the booth. Run it against a running instance.

Verifies, in order:
  1. readiness      - database, content, email queue, model reachability
  2. local model    - whether llama-server/Ollama actually answers
  3. full journey   - profile -> questions -> complete, with timings
  4. narration      - whether Gemma phrasing made it into the result
  5. isolation      - session B cannot read session A's assessment
  6. reset          - delete removes the profile

Usage on the Pi:
    .venv/bin/python scripts/booth_check.py
    .venv/bin/python scripts/booth_check.py --url http://10.42.0.1:8000
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request

PASS = "PASS"
FAIL = "FAIL"
WARN = "WARN"
failures = 0
warnings = 0


def report(status: str, label: str, detail: str = "") -> None:
    global failures, warnings
    if status == FAIL:
        failures += 1
    if status == WARN:
        warnings += 1
    print(f"  [{status}] {label}" + (f" - {detail}" if detail else ""))


def call(base: str, method: str, path: str, body=None, token: str | None = None, timeout: float = 30):
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(base + path, data=data, method=method)
    request.add_header("Content-Type", "application/json")
    if token:
        request.add_header("X-Session-Token", token)
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
            return response.status, (json.loads(raw) if raw else None), (time.perf_counter() - started) * 1000
    except urllib.error.HTTPError as error:
        return error.code, error.read()[:200].decode(errors="replace"), (time.perf_counter() - started) * 1000
    except Exception as error:  # noqa: BLE001
        return 0, str(error)[:200], (time.perf_counter() - started) * 1000


def run_journey(base: str, career_id: str, name: str):
    status, profile, _ = call(base, "POST", "/api/v2/profiles", {
        "first_name": name, "career_id": career_id, "career_stage": "Mid-career",
        "industry": "Business & Finance", "region": "Nairobi",
    })
    if status != 201:
        return None, f"profile creation returned {status}: {profile}"
    session_id, token = profile["session_id"], profile["access_token"]
    status, step, _ = call(base, "POST", f"/api/v2/profiles/{session_id}/assessments", None, token)
    if status != 201:
        return None, f"assessment start returned {status}: {step}"
    assessment_id = step["assessment_id"]
    answered = 0
    while step.get("next_question") and answered < 30:
        question = step["next_question"]
        status, step, _ = call(base, "POST", f"/api/v2/profiles/{session_id}/assessments/{assessment_id}/answers",
                               {"question_id": question["id"], "answer_index": 1}, token)
        if status != 200:
            return None, f"answer returned {status}: {step}"
        answered += 1
    status, result, complete_ms = call(base, "POST",
                                       f"/api/v2/profiles/{session_id}/assessments/{assessment_id}/complete",
                                       None, token, timeout=60)
    if status != 200:
        return None, f"complete returned {status}: {result}"
    return {
        "session_id": session_id, "token": token, "assessment_id": assessment_id,
        "answered": answered, "result": result, "complete_ms": complete_ms,
    }, None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--url", default="http://127.0.0.1:8000", help="base URL of the running app")
    args = parser.parse_args()
    base = args.url.rstrip("/")

    print(f"\nBooth check against {base}\n" + "=" * 58)

    print("\n1. Readiness")
    status, ready, ms = call(base, "GET", "/api/v2/ready", timeout=20)
    if status != 200 or not isinstance(ready, dict):
        report(FAIL, "app is not responding", f"{status} {ready}")
        print("\nThe app is not up. Start it and try again.")
        return 1
    report(PASS if ready.get("status") == "ready" else FAIL, f"status = {ready.get('status')}", f"{ms:.0f}ms")
    database = ready.get("database", {})
    report(PASS if database.get("ok") else FAIL, f"database = {database.get('engine')}",
           f"{database.get('latency_ms')}ms, journal={database.get('journal_mode', 'n/a')}")
    content = ready.get("content", {})
    report(PASS if content.get("valid") else FAIL, "content valid",
           f"{content.get('errors')} errors, {content.get('warnings')} warnings")

    print("\n2. Local model")
    model = ready.get("local_model", {})
    if not model.get("enabled"):
        report(WARN, "no local model configured", "results still work, just without the personal sentence")
    elif model.get("reachable"):
        report(PASS, f"{model.get('backend')} reachable", f"model={model.get('model')}, max_concurrency={model.get('max_concurrency')}")
    else:
        report(WARN, f"{model.get('backend')} NOT reachable", str(model.get("error"))[:80])

    print("\n3. Full journey")
    started = time.perf_counter()
    first, error = run_journey(base, "bank-teller", "BoothA")
    if error:
        report(FAIL, "journey did not complete", error)
        return 1
    total = time.perf_counter() - started
    result = first["result"]["result"]
    report(PASS, f"completed {first['answered']} questions", f"{total:.1f}s total, complete step {first['complete_ms']:.0f}ms")
    report(PASS, f"status = {result['overall']['status']}",
           f"pressure {result['overall']['transformation_pressure']}/100")
    report(PASS if len(result.get("dimensions", {})) == 7 else FAIL,
           f"{len(result.get('dimensions', {}))} dimensions returned")
    report(PASS if result.get("skill_recommendations") else FAIL,
           f"{len(result.get('skill_recommendations', []))} skills recommended")

    print("\n4. Narration (Gemma)")
    if not model.get("enabled"):
        report(WARN, "skipped", "no model configured")
    elif result.get("personal_note"):
        report(PASS, "Gemma wrote the personal sentence", f'"{result["personal_note"][:70]}..."')
    else:
        report(WARN, "no personal sentence", "model unreachable, slow, or busy - static copy was used")

    print("\n5. Session isolation")
    second, error = run_journey(base, "credit-analyst", "BoothB")
    if error:
        report(FAIL, "second session failed", error)
    else:
        status, _, _ = call(base, "GET", f"/api/v2/profiles/{first['session_id']}", None, second["token"])
        report(PASS if status == 401 else FAIL, "B cannot read A's profile", f"got {status}, expected 401")
        status, _, _ = call(base, "GET",
                            f"/api/v2/profiles/{first['session_id']}/assessments/{first['assessment_id']}",
                            None, second["token"])
        report(PASS if status == 401 else FAIL, "B cannot read A's assessment", f"got {status}, expected 401")
        status, _, _ = call(base, "GET", f"/api/v2/profiles/{second['session_id']}", None, second["token"])
        report(PASS if status == 200 else FAIL, "B can read its own profile", f"got {status}, expected 200")

    print("\n6. Session reset")
    status, _, _ = call(base, "DELETE", f"/api/v2/profiles/{first['session_id']}", None, first["token"])
    report(PASS if status == 204 else FAIL, "delete removes the session", f"got {status}, expected 204")
    status, _, _ = call(base, "GET", f"/api/v2/profiles/{first['session_id']}", None, first["token"])
    report(PASS if status == 401 else FAIL, "deleted session is gone", f"got {status}, expected 401")

    print("\n" + "=" * 58)
    if failures:
        print(f"{failures} FAILURE(S), {warnings} warning(s) - do not open the booth yet.")
        return 1
    print(f"All checks passed ({warnings} warning(s)).")
    print(f"Visitors should open: {base.replace('127.0.0.1', '10.42.0.1')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
