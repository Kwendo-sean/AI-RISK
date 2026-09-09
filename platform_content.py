"""Versioned content loader, career taxonomy adapter, search, and validation."""

from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from functools import lru_cache
from pathlib import Path
from typing import Any

from careers_data import CAREERS as LEGACY_CAREERS

CONTENT_DIR = Path(__file__).parent / "content"
DATASET_VERSION = "2.0.0"

SECTOR_FAMILY = {
    "Agriculture & Food": "agriculture",
    "Business & Finance": "business-finance",
    "Healthcare": "healthcare",
    "Information Technology": "information-technology",
    "Education": "education",
    "Engineering": "engineering",
    "Skilled Trades": "skilled-trades",
    "Media & Creative": "media-creative",
    "Legal & Governance": "law-government",
    "Transport & Logistics": "transport-logistics",
    "Hospitality & Tourism": "hospitality-tourism",
    "Social & Community": "social-community",
    "Science & Research": "science-research",
    "Informal Economy": "informal-economy",
    "Energy & Extraction": "energy-extraction",
    "Retail & Property": "retail-property",
    "Public Safety": "public-safety",
    "Sports & Recreation": "sports-recreation",
    "Telecommunications": "telecommunications",
    "Beauty & Fashion": "beauty-fashion",
    "Manufacturing": "manufacturing",
}

FAMILY_TEMPLATES: dict[str, dict[str, Any]] = {
    "agriculture": {
        "responsibilities": ["plan and monitor production", "respond to weather, soil, crop, or animal conditions", "manage supplies, quality, and when to sell"],
        "human": ["reading the land and the seasons", "relationships with suppliers and the community", "coping when nothing is certain"],
        "technical": ["production records", "equipment or husbandry practice", "weather and market interpretation"],
        "tools": ["mobile records", "weather services", "field or livestock equipment"],
        "pathways": ["practical experience", "agricultural training or extension certification"],
        "factors": [46, 72, 82, 58, 45, 45, 70],
        "opportunities": ["precision farming", "advising on climate-ready methods", "selling into markets that demand traceability"],
        "adjacent": ["agricultural technician", "cooperative operations", "agri-input advisory"],
        "tags": ["agriculture", "physical", "local-knowledge", "entrepreneurship", "safety"],
    },
    "business-finance": {
        "responsibilities": ["keep the numbers straight and explain what they mean", "help decide where money and effort go", "keep clients, checks, and colleagues in step"],
        "human": ["business sense", "being trusted with private matters", "keeping everyone informed"],
        "technical": ["financial or operational analysis", "controls and documentation", "digital workflow tools"],
        "tools": ["spreadsheets", "business systems", "reporting software"],
        "pathways": ["business training", "role-specific professional certification"],
        "factors": [70, 25, 38, 55, 68, 70, 58],
        "opportunities": ["handling the cases automation cannot", "advising clients directly", "overseeing how automation is used"],
        "adjacent": ["operations analyst", "business adviser", "risk and controls specialist"],
        "tags": ["finance", "administration", "data", "client-interaction", "regulation"],
    },
    "healthcare": {
        "responsibilities": ["assess health needs", "deliver or coordinate safe care", "record and explain clinical decisions"],
        "human": ["understanding what patients are going through", "patients trusting you", "knowing the right thing to do"],
        "technical": ["clinical assessment", "care protocols", "health information systems"],
        "tools": ["clinical equipment", "health records", "diagnostic systems"],
        "pathways": ["accredited clinical education", "professional registration and continuing development"],
        "factors": [38, 88, 75, 40, 92, 78, 66],
        "opportunities": ["health data and systems", "coordinating care remotely", "AI-assisted note taking"],
        "adjacent": ["health data and systems", "quality improvement", "patient education"],
        "tags": ["healthcare", "human-trust", "regulation", "safety", "emotional-intelligence"],
    },
    "information-technology": {
        "responsibilities": ["design, build, or operate digital systems", "diagnose technical problems", "turn what people need into technology that works"],
        "human": ["seeing how the whole system fits together", "understanding the people who use it", "explaining your work to other teams"],
        "technical": ["software and data fluency", "testing and reliability", "security practice"],
        "tools": ["development environments", "cloud platforms", "monitoring and collaboration tools"],
        "pathways": ["portfolio-based practice", "technical education or certification"],
        "factors": [68, 12, 52, 76, 42, 86, 78],
        "opportunities": ["shipping products with AI help", "security and testing", "joining systems together"],
        "adjacent": ["solutions architecture", "technical product management", "AI operations"],
        "tags": ["software", "data", "creative", "client-interaction"],
    },
    "education": {
        "responsibilities": ["design and deliver learning", "assess progress and adapt support", "keep learners, families, and the school in step"],
        "human": ["keeping learners motivated", "mentoring", "including everyone in the conversation"],
        "technical": ["curriculum design", "assessment practice", "learning technology"],
        "tools": ["learning platforms", "content tools", "student records"],
        "pathways": ["teacher or subject education", "professional registration where required"],
        "factors": [42, 55, 74, 72, 66, 70, 68],
        "opportunities": ["teaching tailored to each learner", "learning design", "coordinating student support"],
        "adjacent": ["instructional design", "education technology", "student success"],
        "tags": ["education", "human-trust", "emotional-intelligence", "creative", "leadership"],
    },
    "engineering": {
        "responsibilities": ["design technical work and check that it holds up", "balance limits, safety, and trade-offs", "keep different teams delivering together"],
        "human": ["experienced judgement", "reaching agreement between sides", "answering for the outcome"],
        "technical": ["engineering analysis", "design standards", "project delivery"],
        "tools": ["CAD or modelling tools", "measurement systems", "project software"],
        "pathways": ["accredited engineering education", "professional registration where applicable"],
        "factors": [52, 48, 64, 72, 78, 76, 70],
        "opportunities": ["digital engineering", "resilient infrastructure", "proving systems work"],
        "adjacent": ["project engineering", "asset management", "technical consulting"],
        "tags": ["engineering", "regulation", "safety", "creative", "management"],
    },
    "skilled-trades": {
        "responsibilities": ["inspect and diagnose physical problems", "build, install, or repair safely", "estimate the work and lay out the options"],
        "human": ["customer trust", "judging what the moment calls for", "the quality of your craft"],
        "technical": ["measurement and diagnostics", "tool and material mastery", "safety practice"],
        "tools": ["hand and power tools", "diagnostic equipment", "job records"],
        "pathways": ["apprenticeship or TVET", "trade licensing where required"],
        "factors": [34, 64, 90, 48, 70, 48, 72],
        "opportunities": ["computer-based fault finding", "installing green systems", "specialist maintenance"],
        "adjacent": ["site supervisor", "technical trainer", "independent contractor"],
        "tags": ["skilled-trades", "physical", "safety", "client-interaction", "self-employed"],
    },
    "media-creative": {
        "responsibilities": ["research and shape the story or idea", "produce and refine creative work", "know your audience and keep their trust"],
        "human": ["knowing what is good work", "explaining one culture to another", "keeping sources and clients on side"],
        "technical": ["production craft", "digital publishing", "rights and verification"],
        "tools": ["creative software", "publishing platforms", "recording or design equipment"],
        "pathways": ["portfolio development", "media, arts, or design training"],
        "factors": [66, 35, 30, 92, 38, 88, 70],
        "opportunities": ["creative direction", "verifying what is real", "AI-assisted production"],
        "adjacent": ["content strategist", "creative producer", "brand systems designer"],
        "tags": ["creative", "design", "media", "client-interaction", "local-knowledge"],
    },
    "law-government": {
        "responsibilities": ["work out what the rules and the evidence mean", "advise or decide within the rules you serve under", "write down decisions you can be held to"],
        "human": ["knowing the right thing to do", "speaking up for people and reaching agreement", "the public trusting you"],
        "technical": ["legal or policy research", "case analysis", "compliance documentation"],
        "tools": ["case or records systems", "research databases", "document tools"],
        "pathways": ["relevant professional or public-service education", "licensing where required"],
        "factors": [56, 45, 25, 54, 90, 72, 62],
        "opportunities": ["setting the rules for AI use", "digital public services", "advising on complex cases"],
        "adjacent": ["compliance", "policy design", "public-sector transformation"],
        "tags": ["law", "government", "regulation", "negotiation", "human-trust"],
    },
    "transport-logistics": {
        "responsibilities": ["move people or goods safely", "react to the road and the conditions you meet", "juggle schedules, equipment, and customers"],
        "human": ["reading the situation around you", "taking responsibility for the customer", "dealing with the cases that do not fit"],
        "technical": ["vehicle or logistics systems", "route planning", "safety checks"],
        "tools": ["vehicles or handling equipment", "navigation", "dispatch and inventory systems"],
        "pathways": ["role-specific licensing", "technical or logistics training"],
        "factors": [55, 45, 72, 22, 68, 62, 56],
        "opportunities": ["fleet data and tracking", "specialist delivery work", "central transport control rooms"],
        "adjacent": ["fleet coordinator", "safety trainer", "logistics operations"],
        "tags": ["transport", "logistics", "physical", "safety", "local-knowledge"],
    },
    "hospitality-tourism": {
        "responsibilities": ["deliver guest service", "coordinate people, facilities, or food", "adjust the experience and put things right when they go wrong"],
        "human": ["knowing what a guest needs", "communicating across cultures", "putting things right for a customer"],
        "technical": ["booking or service systems", "quality and safety practice", "cost control"],
        "tools": ["booking or point-of-sale systems", "service equipment", "review platforms"],
        "pathways": ["hospitality training", "practical service experience"],
        "factors": [48, 74, 68, 66, 52, 60, 65],
        "opportunities": ["designing the guest experience", "pricing and revenue work", "local cultural tourism"],
        "adjacent": ["guest experience", "events operations", "hospitality entrepreneurship"],
        "tags": ["hospitality", "tourism", "client-interaction", "emotional-intelligence", "local-knowledge"],
    },
    "social-community": {
        "responsibilities": ["understand individual and community needs", "line up support and resources", "speak up for people, keep records, and check how it turned out"],
        "human": ["empathy and trust", "bridging between cultures", "making the call in a crisis"],
        "technical": ["case or programme management", "monitoring and evaluation", "safeguarding"],
        "tools": ["case systems", "survey tools", "community communication channels"],
        "pathways": ["social-science or community training", "supervised practice where required"],
        "factors": [34, 92, 52, 58, 72, 58, 68],
        "opportunities": ["programmes shaped by data", "getting more people online", "designing services around the community"],
        "adjacent": ["programme design", "safeguarding", "public engagement"],
        "tags": ["social-community", "human-trust", "emotional-intelligence", "local-knowledge"],
    },
    "science-research": {
        "responsibilities": ["ask the right questions and gather evidence", "work through findings and check they hold up", "explain what is unclear and what it means"],
        "human": ["knowing which findings to trust", "questioning what looks true", "taking responsibility for doing right"],
        "technical": ["experimental or analytical methods", "data interpretation", "quality assurance"],
        "tools": ["laboratory or field instruments", "analysis software", "research databases"],
        "pathways": ["science education", "specialized postgraduate or technical training"],
        "factors": [50, 46, 38, 76, 66, 82, 72],
        "opportunities": ["AI-assisted research", "checking research holds up", "analysis across different fields"],
        "adjacent": ["research operations", "science policy", "quality systems"],
        "tags": ["research", "science", "data", "regulation", "creative"],
    },
    "informal-economy": {
        "responsibilities": ["source and deliver a product or service", "manage customers, cash, and stock", "adapt quickly to local demand"],
        "human": ["being trusted locally", "negotiation", "spotting an opportunity worth taking"],
        "technical": ["trade or service craft", "cash and stock control", "mobile commerce"],
        "tools": ["mobile money", "messaging and social channels", "trade-specific tools"],
        "pathways": ["practical experience", "short business or trade training"],
        "factors": [52, 80, 68, 62, 28, 58, 76],
        "opportunities": ["selling online", "growing on the strength of good records", "specialist local service"],
        "adjacent": ["formalized small business", "cooperative enterprise", "trade specialization"],
        "tags": ["informal-economy", "entrepreneurship", "self-employed", "local-knowledge", "client-interaction"],
    },
}

# Templates for missing families borrow a nearby base and override factors/tags.
FAMILY_TEMPLATES.update({
    "energy-extraction": {**FAMILY_TEMPLATES["engineering"], "tags": ["energy", "physical", "safety", "regulation", "engineering"], "factors": [44, 48, 82, 45, 86, 62, 64]},
    "retail-property": {**FAMILY_TEMPLATES["business-finance"], "tags": ["retail", "property", "sales", "client-interaction", "negotiation"], "factors": [62, 76, 48, 55, 40, 72, 68]},
    "public-safety": {**FAMILY_TEMPLATES["law-government"], "tags": ["public-safety", "physical", "safety", "human-trust", "regulation"], "factors": [30, 88, 88, 35, 94, 58, 66]},
    "sports-recreation": {**FAMILY_TEMPLATES["education"], "tags": ["sports", "physical", "coaching", "human-trust"], "factors": [28, 86, 90, 58, 45, 55, 72]},
    "telecommunications": {**FAMILY_TEMPLATES["information-technology"], "tags": ["telecommunications", "engineering", "physical", "safety"], "factors": [52, 42, 72, 52, 64, 76, 70]},
    "beauty-fashion": {**FAMILY_TEMPLATES["media-creative"], "tags": ["personal-care", "fashion", "creative", "client-interaction", "self-employed"], "factors": [34, 88, 78, 88, 28, 64, 74]},
    "manufacturing": {**FAMILY_TEMPLATES["skilled-trades"], "tags": ["manufacturing", "physical", "safety", "operations"], "factors": [68, 36, 76, 32, 68, 66, 56]},
})

SUPPLEMENTAL_CAREERS = [
    ("smallholder-farmer", "Smallholder Farmer", "Agriculture & Food", "Crop & Mixed Farming", ["farmer", "small-scale farmer", "shamba farmer"], 52),
    ("fisher", "Fisher", "Agriculture & Food", "Capture Fisheries", ["fisherman", "fisherwoman", "artisanal fisher"], 38),
    ("forestry-officer", "Forestry Officer", "Agriculture & Food", "Forestry", ["forester", "forest ranger"], 34),
    ("shopkeeper", "Shopkeeper", "Retail & Property", "Small Retail", ["duka owner", "kiosk owner", "storekeeper"], 61),
    ("retail-associate", "Retail Sales Associate", "Retail & Property", "Retail", ["shop assistant", "sales attendant"], 68),
    ("real-estate-agent", "Real Estate Agent", "Retail & Property", "Property", ["realtor", "property agent"], 46),
    ("construction-worker", "Construction Worker", "Skilled Trades", "Construction", ["site worker", "building labourer"], 35),
    ("solar-technician", "Solar Installation Technician", "Energy & Extraction", "Renewable Energy", ["solar installer", "solar PV technician"], 28),
    ("mining-technician", "Mining Technician", "Energy & Extraction", "Mining", ["mine technician", "mineral extraction technician"], 48),
    ("plant-operator", "Manufacturing Plant Operator", "Manufacturing", "Industrial Production", ["machine operator", "factory operator"], 72),
    ("quality-technician", "Manufacturing Quality Technician", "Manufacturing", "Quality", ["quality inspector", "QA technician"], 49),
    ("telecom-technician", "Telecommunications Technician", "Telecommunications", "Network Field Service", ["fibre technician", "telecoms technician"], 43),
    ("call-centre-supervisor", "Call Centre Supervisor", "Business & Finance", "Customer Service", ["contact centre supervisor", "call center team lead"], 63),
    ("hairdresser", "Hairdresser or Barber", "Beauty & Fashion", "Personal Care", ["barber", "hairstylist", "salon professional"], 24),
    ("fashion-designer", "Fashion Designer", "Beauty & Fashion", "Fashion", ["clothing designer", "apparel designer"], 44),
    ("content-creator", "Digital Content Creator", "Media & Creative", "Creator Economy", ["influencer", "YouTuber", "TikTok creator", "podcaster"], 58),
    ("police-officer", "Police Officer", "Public Safety", "Law Enforcement", ["law enforcement officer", "police constable"], 24),
    ("firefighter", "Firefighter", "Public Safety", "Emergency Response", ["fire officer", "fire and rescue officer"], 18),
    ("fitness-trainer", "Fitness Trainer", "Sports & Recreation", "Fitness", ["personal trainer", "gym instructor"], 27),
    ("sports-coach", "Sports Coach", "Sports & Recreation", "Coaching", ["athletics coach", "team coach"], 22)
]

ROLE_OVERRIDES = {
    "nurse": {"defensive": ["patient_communication", "clinical_documentation_ai"], "growth": ["clinical_informatics"]},
    "smallholder-farmer": {"defensive": ["climate_risk_planning", "farm_record_analysis"], "growth": ["precision_agriculture"]},
    "farm-manager": {"defensive": ["climate_risk_planning", "farm_record_analysis"], "growth": ["precision_agriculture"]},
    "accountant": {"defensive": ["financial_controls", "ai_reconciliation"], "growth": ["advisory_communication"]},
    "auto-mechanic": {"defensive": ["electronic_diagnostics", "repair_trust"], "growth": ["ev_servicing"]},
    "graphic-designer": {"defensive": ["creative_direction", "creative_ip"], "growth": ["ai_workflow_orchestration"]},
}


def normalize(value: str) -> str:
    raw = unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode()
    return " ".join(re.findall(r"[a-z0-9]+", raw.lower()))


def _specific_tags(career_id: str, title: str, family: str, sector: str) -> list[str]:
    tags = set(FAMILY_TEMPLATES[family]["tags"])
    tags.update(normalize(title).split())
    tags.add(family)
    tags.add(normalize(sector).replace(" ", "-"))
    if any(x in career_id for x in ("manager", "officer", "supervisor")):
        tags.update(("management", "leadership"))
    return sorted(tags)


def _career_record(raw: dict[str, Any]) -> dict[str, Any]:
    family = SECTOR_FAMILY.get(raw["sector"], "business-finance")
    template = FAMILY_TEMPLATES[family]
    factors = template["factors"]
    title = raw["title"]
    existing_skills = list(raw.get("skills", []))
    recommendations = ROLE_OVERRIDES.get(raw["id"], {})
    return {
        "id": raw["id"],
        "canonical_title": title,
        "alternative_titles": sorted(set(raw.get("alt", []))),
        "industry": raw["sector"],
        "sub_industry": raw.get("sub", "General"),
        "career_family": family,
        "typical_responsibilities": template["responsibilities"],
        "core_human_skills": template["human"],
        "technical_skills": existing_skills[:4] or template["technical"],
        "tools_commonly_used": template["tools"],
        "education_certification_pathways": template["pathways"],
        "routine_task_percentage": int(raw.get("risk", factors[0]) * 0.72),
        "human_interaction_intensity": factors[1],
        "physical_world_requirement": factors[2],
        "creativity_requirement": factors[3],
        "decision_making_responsibility": factors[4],
        "regulatory_safety_sensitivity": factors[4],
        "ai_exposure": int(raw.get("risk", factors[0])),
        "automation_potential": factors[0],
        "ai_augmentation_potential": factors[5],
        "estimated_transformation_horizon": "Tasks are already changing; material workflow change is plausible within 2–5 years.",
        "emerging_opportunities": template["opportunities"],
        "adjacent_career_paths": template["adjacent"],
        "recommended_defensive_skills": recommendations.get("defensive", ["ai_output_verification", "workflow_mapping"]),
        "recommended_growth_skills": recommendations.get("growth", ["technical_systems_thinking", "data_storytelling"]),
        "relevant_question_modules": _specific_tags(raw["id"], title, family, raw["sector"]),
        "geographic_market_considerations": ["Technology access, regulation, infrastructure, wages, and adoption differ by country and local market.", "Informal and self-employed work may transform differently from formal payroll roles."],
        "evidence": {"coverage": "foundational", "method": "editorial seed profile; task-level user answers adjust the assessment", "sources": [], "last_reviewed": "2026-09-04"},
        "dataset_version": DATASET_VERSION,
        "legacy_workforce_estimate": raw.get("workforce"),
        "is_technical": bool(raw.get("is_technical")),
        "roadmap_slug": raw.get("roadmap_slug"),
        "search_tags": _specific_tags(raw["id"], title, family, raw["sector"]),
    }


def build_career_seed() -> tuple[dict[str, Any], ...]:
    raw = [dict(c) for c in LEGACY_CAREERS]
    for cid, title, sector, sub, aliases, risk in SUPPLEMENTAL_CAREERS:
        raw.append({"id": cid, "title": title, "sector": sector, "sub": sub, "alt": aliases, "risk": risk, "skills": [], "workforce": None, "is_technical": False, "roadmap_slug": None})
    return tuple(_career_record(item) for item in raw)


@lru_cache(maxsize=1)
def load_careers() -> tuple[dict[str, Any], ...]:
    path = CONTENT_DIR / "careers.v1.json"
    if path.exists():
        document = json.loads(path.read_text(encoding="utf-8"))
        if document.get("dataset_version") != DATASET_VERSION:
            raise ValueError("Career seed version does not match application content version")
        return tuple(document["careers"])
    return build_career_seed()


@lru_cache(maxsize=1)
def career_index() -> dict[str, dict[str, Any]]:
    return {career["id"]: career for career in load_careers()}


@lru_cache(maxsize=1)
def load_questions() -> dict[str, Any]:
    return json.loads((CONTENT_DIR / "questions.v1.json").read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def load_skills() -> dict[str, Any]:
    return json.loads((CONTENT_DIR / "skills.v1.json").read_text(encoding="utf-8"))


def get_career(career_id: str) -> dict[str, Any] | None:
    return career_index().get(career_id)


def fallback_career(description: str, industry: str = "Other") -> dict[str, Any]:
    text = (description or "Unlisted role").strip()[:160]
    tags = set(normalize(text).split())
    family = "informal-economy" if tags & {"owner", "seller", "trader", "freelance", "farmer"} else "business-finance"
    template = FAMILY_TEMPLATES[family]
    record = _career_record({"id": "custom-role", "title": text, "sector": industry or "Other", "sub": "User-described role", "alt": [], "risk": template["factors"][0], "skills": [], "workforce": None, "is_technical": False, "roadmap_slug": None})
    record["career_family"] = family
    record["evidence"] = {"coverage": "fallback", "method": "general task-characteristic assessment; no title-specific evidence", "sources": [], "last_reviewed": "2026-09-04"}
    record["geographic_market_considerations"] = ["This role was not in the seed taxonomy. Results rely more heavily on your task-level answers."]
    return record


@lru_cache(maxsize=1)
def _search_index() -> dict[str, tuple[str, tuple[str, ...], tuple[str, ...]]]:
    """Normalised title/alias/haystack tuples per career, built once."""
    index = {}
    for career in load_careers():
        title = normalize(career["canonical_title"])
        aliases = tuple(normalize(v) for v in career["alternative_titles"])
        extras = (normalize(career["sub_industry"]), normalize(career["industry"]))
        tags = tuple(normalize(tag) for tag in career.get("search_tags", []))
        base = (title, *aliases, *extras, *tags)
        squashed = tuple({v.replace(" ", "") for v in base if " " in v and len(v) <= 24})
        index[career["id"]] = (title, aliases, base + squashed)
    return index


def _title_and_aliases(career_id: str) -> tuple[str, list[str]]:
    title, aliases, _ = _search_index()[career_id]
    return title, list(aliases)


def _haystacks(career_id: str) -> tuple[str, ...]:
    return _search_index()[career_id][2]


def search_careers(query: str = "", industry: str | None = None, limit: int = 30) -> list[dict[str, Any]]:
    q = normalize(query)
    # One-letter tokens carry no signal and match noise ("m-pesa" should not pull in "m&a analyst").
    q_tokens = {token for token in q.split() if len(token) > 1}
    scored: list[tuple[float, dict[str, Any]]] = []
    for career in load_careers():
        if industry and industry != "All" and career["industry"] != industry:
            continue
        title, aliases = _title_and_aliases(career["id"])
        haystacks = _haystacks(career["id"])
        if not q:
            score = 1.0
        else:
            exact = 120 if q == title or q in aliases else 0
            prefix = 50 if title.startswith(q) or any(a.startswith(q) for a in aliases) else 0
            contains = 35 if any(q in value for value in haystacks) else 0
            token_overlap = max((len(q_tokens & set(value.split())) / max(1, len(q_tokens)) for value in haystacks), default=0) * 60
            # A hit in the job's own name beats the same hit in an alias or a tag.
            title_bonus = 15 if q_tokens & set(title.split()) or title.startswith(q) else 0
            literal = exact + prefix + contains + token_overlap + title_bonus
            if literal:
                score = literal
            else:
                # Fuzzy matching exists to rescue typos, not to surface rhymes ("teller"
                # must not return "welder"). Only reachable when nothing matched literally,
                # and pre-filtered so the expensive comparison runs on a handful of strings.
                if len(q) < 4:
                    continue
                candidates = [v for v in haystacks if v and v[0] == q[0] and abs(len(v) - len(q)) <= 4]
                if not candidates:
                    continue
                ratio = max(SequenceMatcher(None, q, value).ratio() for value in candidates)
                if ratio < 0.82:
                    continue
                score = ratio * 40
        scored.append((score, career))
    scored.sort(key=lambda pair: (-pair[0], pair[1]["canonical_title"]))
    return [career for _, career in scored[: max(1, min(limit, 100))]]


def public_career_summary(career: dict[str, Any]) -> dict[str, Any]:
    return {key: career[key] for key in ("id", "canonical_title", "alternative_titles", "industry", "sub_industry", "career_family", "ai_exposure", "ai_augmentation_potential", "evidence")}


@lru_cache(maxsize=4)
def validate_content(similarity_threshold: float = 0.88) -> dict[str, Any]:
    careers = load_careers()
    questions_doc = load_questions()
    skills_doc = load_skills()
    errors: list[str] = []
    warnings: list[str] = []

    def duplicate_ids(items: list[dict[str, Any]], key: str, label: str) -> None:
        counts = Counter(item.get(key) for item in items)
        errors.extend(f"duplicate {label} id: {value}" for value, count in counts.items() if value and count > 1)

    duplicate_ids(list(careers), "id", "career")
    questions = questions_doc["questions"]
    skills = skills_doc["skills"]
    duplicate_ids(questions, "id", "question")
    duplicate_ids(skills, "skill_id", "skill")
    required_question = {"id", "construct_id", "text", "response_type", "career_tags", "industry_tags", "seniority_tags", "scoring", "weight", "why_asked"}
    required_skill = {"skill_id", "name", "category", "description", "why", "difficulty", "time_to_develop", "impact", "first_action", "learning_pathway", "xp_reward", "unlock", "career_tags", "prerequisites"}
    for question in questions:
        missing = required_question - set(question)
        if missing:
            errors.append(f"question {question.get('id')} missing {sorted(missing)}")
        if not question.get("scoring"):
            errors.append(f"question {question.get('id')} has no scoring effect")
        answers = question.get("answers") or questions_doc["response_sets"].get(question.get("response_set", ""))
        if not answers or any(len(values) != len(answers) for values in question.get("scoring", {}).values()):
            errors.append(f"question {question.get('id')} has contradictory scoring/answer lengths")
    for skill in skills:
        missing = required_skill - set(skill)
        if missing:
            errors.append(f"skill {skill.get('skill_id')} missing {sorted(missing)}")
    for items, id_key, text_key, kind in ((questions, "id", "text", "question"), (skills, "skill_id", "name", "skill")):
        for i, left in enumerate(items):
            for right in items[i + 1 :]:
                ratio = SequenceMatcher(None, normalize(left[text_key]), normalize(right[text_key])).ratio()
                if ratio >= similarity_threshold:
                    warnings.append(f"near-duplicate {kind}: {left[id_key]} / {right[id_key]} ({ratio:.2f})")
    represented = Counter(c["career_family"] for c in careers)
    mapped_skill_ids = {sid for c in careers for sid in c["recommended_defensive_skills"] + c["recommended_growth_skills"]}
    known_skill_ids = {s["skill_id"] for s in skills}
    for sid in sorted(mapped_skill_ids - known_skill_ids):
        errors.append(f"career mapping references missing skill: {sid}")
    return {
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "coverage": {
            "dataset_version": DATASET_VERSION,
            "careers": len(careers),
            "career_families": dict(sorted(represented.items())),
            "question_records": len(questions),
            "question_constructs": len({q["construct_id"] for q in questions}),
            "skills": len(skills),
            "fallback_careers": sum(c["evidence"]["coverage"] == "fallback" for c in careers),
        },
    }


def select_skills(career: dict[str, Any], dimensions: dict[str, int], limit: int = 6) -> list[dict[str, Any]]:
    all_skills = load_skills()["skills"]
    tags = set(career["search_tags"]) | {career["id"], career["career_family"]}
    priority = career["recommended_defensive_skills"] + career["recommended_growth_skills"]
    scores: dict[str, float] = defaultdict(float)
    for index, skill_id in enumerate(priority):
        scores[skill_id] += 50 - index
    for skill in all_skills:
        skill_tags = set(skill["career_tags"])
        scores[skill["skill_id"]] += len(tags & skill_tags) * 8
        if "*" in skill_tags:
            scores[skill["skill_id"]] += 4
        if dimensions.get("career_adaptability", 50) < 45 and skill["category"] == "AI literacy":
            scores[skill["skill_id"]] += 6
        if dimensions.get("human_advantage", 50) < 45 and skill["category"] == "Human and interpersonal skills":
            scores[skill["skill_id"]] += 5
    ranked = sorted(all_skills, key=lambda skill: (-scores[skill["skill_id"]], skill["name"]))
    return ranked[: max(1, min(limit, 8))]
