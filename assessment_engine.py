"""Deterministic adaptive-question routing and explainable multidimensional scoring."""

from __future__ import annotations

import hashlib
from typing import Any

from platform_content import load_questions, select_skills

DIMENSIONS = (
    "automation_exposure",
    "augmentation_opportunity",
    "human_advantage",
    "physical_defensibility",
    "accountability_protection",
    "reskilling_urgency",
    "career_adaptability",
)

CORE_CONSTRUCTS = (
    "routine_intensity",
    "physical_presence",
    "human_trust",
    "accountability",
    "data_handling",
    "analytical_reasoning",
    "ai_adoption",
    "communication",
    "domain_expertise",
    "work_environment",
    "income_model",
    "recent_transformation",
)

TAG_CONSTRUCTS = {
    "agriculture": ("local_knowledge", "safety_judgment", "entrepreneurship"),
    "physical": ("safety_judgment",),
    "skilled-trades": ("client_interaction", "safety_judgment"),
    "transport": ("safety_judgment", "local_knowledge"),
    "healthcare": ("regulation_compliance", "emotional_intelligence", "safety_judgment"),
    "education": ("emotional_intelligence", "creative_originality"),
    "creative": ("creative_originality", "client_interaction"),
    "media": ("creative_originality", "local_knowledge"),
    "law": ("regulation_compliance", "negotiation"),
    "government": ("regulation_compliance", "local_knowledge"),
    "finance": ("regulation_compliance", "client_interaction"),
    "management": ("leadership", "negotiation"),
    "leadership": ("leadership", "negotiation"),
    "informal-economy": ("entrepreneurship", "local_knowledge", "client_interaction"),
    "self-employed": ("entrepreneurship", "client_interaction"),
    "retail": ("client_interaction", "negotiation"),
    "hospitality": ("client_interaction", "emotional_intelligence"),
    "public-safety": ("safety_judgment", "regulation_compliance", "leadership"),
    "engineering": ("safety_judgment", "regulation_compliance", "creative_originality"),
}

STAGE_TAGS = {
    "Manager or executive": ("leadership", "negotiation"),
    "Founder or self-employed": ("entrepreneurship", "client_interaction"),
    "Career changer": ("learning_adaptability",),
    "Currently unemployed or exploring": ("learning_adaptability",),
    "Student": ("learning_adaptability",),
}


def _answers_for(question: dict[str, Any], document: dict[str, Any]) -> list[str]:
    return question.get("answers") or document["response_sets"][question["response_set"]]


def question_public(question: dict[str, Any], document: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": question["id"],
        "construct_id": question["construct_id"],
        "text": question["text"],
        "response_type": question["response_type"],
        "answers": [{"value": index, "label": label} for index, label in enumerate(_answers_for(question, document))],
        "why_asked": question["why_asked"],
    }


def select_question_ids(career: dict[str, Any], profile: dict[str, Any]) -> list[str]:
    """Select one question per construct, preferring role-specific wording."""
    document = load_questions()
    questions = document["questions"]
    tags = set(career["relevant_question_modules"]) | {career["career_family"], career["id"]}
    stage = profile.get("career_stage", "")
    constructs = list(CORE_CONSTRUCTS)
    for tag in sorted(tags):
        for construct in TAG_CONSTRUCTS.get(tag, ()):
            if construct not in constructs:
                constructs.append(construct)
    for construct in STAGE_TAGS.get(stage, ()):
        if construct not in constructs:
            constructs.append(construct)
    constructs = constructs[:16]
    chosen: list[str] = []
    for construct in constructs:
        candidates = [q for q in questions if q["construct_id"] == construct]
        if not candidates:
            continue
        def relevance(q: dict[str, Any]) -> tuple[int, str]:
            qtags = set(q["career_tags"])
            return (len(tags & qtags) * 10 + (0 if "*" in qtags else 2), q["id"])
        candidates.sort(key=relevance, reverse=True)
        chosen.append(candidates[0]["id"])
    # Stable ordering within a career/profile while keeping the early experience varied.
    seed = f"{career['id']}|{stage}|{load_questions()['dataset_version']}"
    head, tail = chosen[:4], chosen[4:]
    tail.sort(key=lambda qid: hashlib.sha256(f"{seed}|{qid}".encode()).hexdigest())
    return head + tail


def adapt_question_ids(question_ids: list[str], answers: dict[str, int]) -> list[str]:
    """Use early answers to add a documented follow-up without duplicate constructs."""
    document = load_questions()
    by_id = {q["id"]: q for q in document["questions"]}
    constructs = {by_id[qid]["construct_id"] for qid in question_ids}
    adoption = answers.get("q_ai_adoption_v1")
    if adoption is not None and adoption <= 1 and "learning_adaptability" not in constructs:
        question_ids = [*question_ids, "q_learning_v1"]
    return question_ids[:16]


def questions_by_ids(question_ids: list[str]) -> list[dict[str, Any]]:
    document = load_questions()
    by_id = {q["id"]: q for q in document["questions"]}
    return [question_public(by_id[qid], document) for qid in question_ids if qid in by_id]


def score_assessment(career: dict[str, Any], question_ids: list[str], answers: dict[str, int]) -> dict[str, Any]:
    document = load_questions()
    by_id = {q["id"]: q for q in document["questions"]}
    totals = {dimension: 0.0 for dimension in DIMENSIONS}
    weights = {dimension: 0.0 for dimension in DIMENSIONS}
    impacts: list[dict[str, Any]] = []

    for question_id in question_ids:
        if question_id not in answers or question_id not in by_id:
            continue
        question = by_id[question_id]
        answer_index = int(answers[question_id])
        labels = _answers_for(question, document)
        if not 0 <= answer_index < len(labels):
            continue
        contribution = 0.0
        for dimension, values in question["scoring"].items():
            raw = float(values[answer_index]) / max(1.0, float(max(values))) * 100
            weight = float(question["weight"])
            totals[dimension] += raw * weight
            weights[dimension] += weight
            contribution += abs(raw - 50) * weight
        impacts.append({
            "question_id": question_id,
            "construct_id": question["construct_id"],
            "answer": labels[answer_index],
            "effect_strength": round(contribution, 1),
            "explanation": question["why_asked"],
        })

    base = {
        "automation_exposure": career["automation_potential"],
        "augmentation_opportunity": career["ai_augmentation_potential"],
        "human_advantage": career["human_interaction_intensity"],
        "physical_defensibility": career["physical_world_requirement"],
        "accountability_protection": career["regulatory_safety_sensitivity"],
        "reskilling_urgency": career["ai_exposure"],
        "career_adaptability": 50,
    }
    dimensions: dict[str, int] = {}
    for dimension in DIMENSIONS:
        answer_score = totals[dimension] / weights[dimension] if weights[dimension] else base[dimension]
        answer_share = 0.72 if career["evidence"]["coverage"] == "fallback" else 0.58
        dimensions[dimension] = round(base[dimension] * (1 - answer_share) + answer_score * answer_share)

    protective = (
        dimensions["human_advantage"]
        + dimensions["physical_defensibility"]
        + dimensions["accountability_protection"]
        + dimensions["career_adaptability"]
    ) / 4
    pressure = round(
        dimensions["automation_exposure"] * 0.62
        + dimensions["reskilling_urgency"] * 0.23
        - protective * 0.25
        + 20
    )
    pressure = max(0, min(100, pressure))
    if pressure >= 68:
        status = "your job is changing fast"
        tone = "urgent"
    elif pressure >= 48:
        status = "your job is starting to change"
        tone = "watch"
    elif dimensions["augmentation_opportunity"] >= 68:
        status = "AI could make you a lot faster"
        tone = "opportunity"
    else:
        status = "your work is hard to replace"
        tone = "guarded"

    confidence = "limited" if career["evidence"]["coverage"] == "fallback" else "developing"
    answered = len(answers)
    if career["evidence"]["coverage"] != "fallback" and answered >= 12:
        confidence = "moderate"
    impacts.sort(key=lambda item: item["effect_strength"], reverse=True)
    likely = [
        responsibility for responsibility in career["typical_responsibilities"]
        if any(word in responsibility for word in ("document", "record", "analy", "coordinate"))
    ][:3] or career["typical_responsibilities"][:2]
    durable = career["core_human_skills"][:3]
    skills = select_skills(career, dimensions, 6)
    return {
        "overall": {"status": status, "tone": tone, "transformation_pressure": pressure},
        "dimensions": dimensions,
        "confidence": {"level": confidence, "answered_questions": answered, "career_coverage": career["evidence"]["coverage"], "note": "Coverage reflects how much profile data we hold for this role."},
        "top_answer_influences": impacts[:5],
        "tasks_most_likely_to_change": likely,
        "tasks_least_likely_to_be_automated": durable,
        "skill_recommendations": skills,
        "emerging_opportunities": career["emerging_opportunities"],
        "adjacent_career_paths": career["adjacent_career_paths"],
        "model_version": "assessment-1.0.0",
    }

