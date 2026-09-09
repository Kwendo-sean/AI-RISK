"""Recompute career AI-exposure scores from published research datasets.

Inputs
------
data/sources/microsoft_working_with_ai_soc_metrics.csv
    Tomlinson, Jaffe, Wang, Counts & Suri (2025), "Working with AI: Measuring the
    Applicability of Generative AI to Occupations" (arXiv:2507.07935). Derived from
    200k anonymised Bing Copilot conversations, aggregated to 2018 SOC codes.
    Licence: CC BY 4.0. Vendored in this repository with attribution.

data/cache/aioe_appendix_a.csv  (run scripts/fetch_sources.py first)
    Felten, Raj & Seamans (2021), "Occupational, industry, and geographic exposure
    to artificial intelligence", Strategic Management Journal 42(12): 2195-2217.
    AI Occupational Exposure (AIOE) z-scores by 2018 SOC code.

content/soc_crosswalk.json
    Our 141 careers mapped to SOC occupations, with a match-quality flag.

Outputs
-------
Rewrites ai_exposure, ai_augmentation_potential and the evidence block of every
career in content/careers.v1.json.

Method
------
ai_exposure            = percentile rank of (0.6 * MS "AI performs the activity"
                         score + 0.4 * normalised AIOE), across all mapped careers.
ai_augmentation_potential
                       = percentile rank of the MS "user asks AI for help" score.

Both are reported as 0-100 positions relative to the other occupations in this
dataset, not as probabilities of job loss. Percentile framing is deliberate: the
underlying measures are relative indices, so an absolute reading would overclaim.

Usage: python scripts/build_career_evidence.py [--dry-run]
"""
from __future__ import annotations

import csv
import json
import sys
from bisect import bisect_left
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CAREERS = ROOT / "content" / "careers.v1.json"
CROSSWALK = ROOT / "content" / "soc_crosswalk.json"
MS_METRICS = ROOT / "data" / "sources" / "microsoft_working_with_ai_soc_metrics.csv"
AIOE_CSV = ROOT / "data" / "cache" / "aioe_appendix_a.csv"

MS_CITATION = {
    "id": "microsoft-working-with-ai-2025",
    "title": "Working with AI: Measuring the Applicability of Generative AI to Occupations",
    "publisher": "Microsoft Research",
    "year": 2025,
    "url": "https://arxiv.org/abs/2507.07935",
    "licence": "CC BY 4.0",
}
AIOE_CITATION = {
    "id": "felten-raj-seamans-aioe-2021",
    "title": "Occupational, industry, and geographic exposure to artificial intelligence",
    "publisher": "Strategic Management Journal 42(12): 2195-2217",
    "year": 2021,
    "url": "https://doi.org/10.1002/smj.3286",
    "licence": "cited, not redistributed",
}
ILO_CITATION = {
    "id": "ilo-wp140-2025",
    "title": "Generative AI and Jobs: A Refined Global Index of Occupational Exposure (Working Paper 140)",
    "publisher": "International Labour Organization",
    "year": 2025,
    "url": "https://www.ilo.org/publications/generative-ai-and-jobs-refined-global-index-occupational-exposure",
    "licence": "cited for methodology and developing-economy context",
}


def load_ms_metrics() -> dict[str, dict[str, float]]:
    if not MS_METRICS.exists():
        raise SystemExit(f"missing {MS_METRICS}")
    metrics: dict[str, dict[str, float]] = {}
    with MS_METRICS.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            code = (row.get("SOC Code") or "").strip()
            if not code:
                continue
            try:
                metrics[code] = {
                    "title": row["title"],
                    "ai_performs": float(row["ai_applicability_score_ai_nonphysical"]),
                    "user_asks": float(row["ai_applicability_score_user"]),
                    "coverage_ai": float(row["coverage_ai"]),
                }
            except (KeyError, TypeError, ValueError):
                continue
    return metrics


def load_aioe() -> dict[str, float]:
    if not AIOE_CSV.exists():
        print(f"note: {AIOE_CSV} not found - run scripts/fetch_sources.py for the AIOE component")
        return {}
    scores: dict[str, float] = {}
    with AIOE_CSV.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            try:
                scores[row["soc_code"].strip()] = float(row["aioe"])
            except (KeyError, TypeError, ValueError):
                continue
    return scores


def percentile(sorted_values: list[float], value: float) -> int:
    """Position of `value` within `sorted_values`, as 0-100."""
    if len(sorted_values) < 2:
        return 50
    rank = bisect_left(sorted_values, value)
    return round(rank / (len(sorted_values) - 1) * 100)


def main() -> int:
    dry_run = "--dry-run" in sys.argv
    ms = load_ms_metrics()
    aioe = load_aioe()
    crosswalk = json.loads(CROSSWALK.read_text(encoding="utf-8"))["careers"]
    payload = json.loads(CAREERS.read_text(encoding="utf-8"))

    missing_map = [c["id"] for c in payload["careers"] if c["id"] not in crosswalk]
    if missing_map:
        raise SystemExit(f"crosswalk is missing {len(missing_map)} careers: {missing_map[:10]}")

    unmatched: list[tuple[str, str]] = []
    raw: dict[str, dict[str, float | str]] = {}
    aioe_values = [v for v in aioe.values()]
    aioe_lo, aioe_hi = (min(aioe_values), max(aioe_values)) if aioe_values else (0.0, 1.0)

    for career in payload["careers"]:
        soc, quality = crosswalk[career["id"]]
        row = ms.get(soc)
        if not row:
            unmatched.append((career["id"], soc))
            continue
        blended = row["ai_performs"]
        if soc in aioe:
            normalised = (aioe[soc] - aioe_lo) / (aioe_hi - aioe_lo or 1)
            blended = 0.6 * row["ai_performs"] + 0.4 * normalised * max(
                r["ai_performs"] for r in ms.values()
            )
        raw[career["id"]] = {
            "soc": soc,
            "quality": quality,
            "soc_title": row["title"],
            "blended": blended,
            "user_asks": row["user_asks"],
            "ai_performs": row["ai_performs"],
            "aioe": aioe.get(soc),
        }

    if unmatched:
        print(f"WARNING: {len(unmatched)} careers have SOC codes absent from the dataset:")
        for career_id, soc in unmatched:
            print(f"  {career_id} -> {soc}")

    exposure_scale = sorted(float(v["blended"]) for v in raw.values())
    augment_scale = sorted(float(v["user_asks"]) for v in raw.values())

    changes = 0
    for career in payload["careers"]:
        entry = raw.get(career["id"])
        if not entry:
            career["evidence"] = {
                "coverage": "fallback",
                "method": "no matching occupation in the source datasets; scores left as an editorial estimate",
                "sources": [],
                "last_reviewed": str(date.today()),
            }
            continue
        exposure = percentile(exposure_scale, float(entry["blended"]))
        augmentation = percentile(augment_scale, float(entry["user_asks"]))
        if career["ai_exposure"] != exposure or career["ai_augmentation_potential"] != augmentation:
            changes += 1
        career["ai_exposure"] = exposure
        career["ai_augmentation_potential"] = augmentation
        sources = [MS_CITATION, ILO_CITATION]
        if entry["aioe"] is not None:
            sources.insert(1, AIOE_CITATION)
        career["evidence"] = {
            "coverage": {"direct": "measured", "close": "measured", "analogue": "indicative"}[str(entry["quality"])],
            "method": (
                f"Scored from the {entry['soc_title']} occupation (SOC {entry['soc']}, {entry['quality']} match). "
                "Exposure is a percentile of observed generative-AI task overlap blended with the AIOE index; "
                "augmentation is a percentile of how often workers ask AI for help with those tasks. "
                "Positions are relative to the other careers in this dataset, not probabilities of job loss."
            ),
            "sources": sources,
            "soc_code": entry["soc"],
            "soc_title": entry["soc_title"],
            "match_quality": entry["quality"],
            "inputs": {
                "ms_ai_performs": round(float(entry["ai_performs"]), 4),
                "ms_user_asks": round(float(entry["user_asks"]), 4),
                "aioe_z": round(float(entry["aioe"]), 4) if entry["aioe"] is not None else None,
            },
            "last_reviewed": str(date.today()),
        }

    payload["dataset_version"] = "2.0.0"
    payload["evidence_build"] = {
        "generated": str(date.today()),
        "crosswalk_version": json.loads(CROSSWALK.read_text(encoding="utf-8"))["crosswalk_version"],
        "aioe_available": bool(aioe),
        "careers_scored": len(raw),
        "careers_unmatched": len(unmatched),
    }

    if dry_run:
        ranked = sorted(payload["careers"], key=lambda c: c["ai_exposure"], reverse=True)
        print("\nhighest exposure:")
        for career in ranked[:12]:
            print(f"  {career['ai_exposure']:3d}  {career['canonical_title']}")
        print("lowest exposure:")
        for career in ranked[-12:]:
            print(f"  {career['ai_exposure']:3d}  {career['canonical_title']}")
        print(f"\n(dry run - {changes} careers would change)")
        return 0

    CAREERS.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"rewrote {CAREERS.name}: {len(raw)} careers scored, {changes} values changed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
