"""Add banking and financial-services careers to the seed.

The seed carried a single banking role (Bank Teller) for the whole sector, so
anyone searching "bank", "credit", "loans" or "SACCO" found almost nothing. This
adds the roles that actually staff a Kenyan bank, SACCO or microfinance branch.

Records inherit the business-finance family template and override the parts that
are genuinely role-specific: titles, search terms, task mix and skills. Scores are
left at zero here on purpose - scripts/build_career_evidence.py fills in
ai_exposure and ai_augmentation_potential from the research datasets afterwards.

Idempotent: re-running skips careers that already exist.

Usage: python scripts/add_banking_careers.py && python scripts/build_career_evidence.py
"""
from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CAREERS = ROOT / "content" / "careers.v1.json"
CROSSWALK = ROOT / "content" / "soc_crosswalk.json"

# id, title, sub-industry, aliases, SOC, match quality, task mix overrides, skills
NEW_CAREERS: list[dict] = [
    {
        "id": "relationship-manager", "title": "Relationship Manager", "sub": "Banking", "soc": "41-3031", "quality": "close",
        "aliases": ["account relationship manager", "corporate banker", "business banker", "client manager"],
        "mix": {"routine_task_percentage": 38, "human_interaction_intensity": 88, "decision_making_responsibility": 72},
        "technical": ["Credit appraisal", "Portfolio growth", "Product structuring", "Client negotiation"],
        "responsibilities": ["grow and keep a book of clients", "match products to what a client actually needs", "spot credit trouble before it lands"],
        "human": ["being trusted with private matters", "reading people", "negotiating"],
    },
    {
        "id": "credit-analyst", "title": "Credit Analyst", "sub": "Banking", "soc": "13-2041", "quality": "direct",
        "aliases": ["credit officer", "credit appraisal officer", "lending analyst"],
        "mix": {"routine_task_percentage": 62, "human_interaction_intensity": 42, "decision_making_responsibility": 74},
        "technical": ["Financial statement analysis", "Credit scoring models", "Sector risk assessment", "Covenant monitoring"],
        "responsibilities": ["read financial statements and judge whether to lend", "size up the risk in a sector or a borrower", "write the case that a committee will sign off"],
        "human": ["experienced judgement", "knowing the right thing to do", "keeping everyone informed"],
    },
    {
        "id": "loan-officer", "title": "Loan Officer", "sub": "Banking", "soc": "13-2072", "quality": "direct",
        "aliases": ["lending officer", "credit sales officer", "asset finance officer"],
        "mix": {"routine_task_percentage": 58, "human_interaction_intensity": 76, "decision_making_responsibility": 62},
        "technical": ["Loan origination", "Affordability assessment", "Security and collateral", "Arrears follow-up"],
        "responsibilities": ["take a borrower from application to disbursement", "check that repayments are actually affordable", "chase and restructure what falls behind"],
        "human": ["being trusted with private matters", "reading people", "putting things right for a customer"],
    },
    {
        "id": "bank-branch-manager", "title": "Bank Branch Manager", "sub": "Banking", "soc": "11-3031", "quality": "close",
        "aliases": ["branch manager", "banking centre manager", "branch operations manager"],
        "mix": {"routine_task_percentage": 40, "human_interaction_intensity": 84, "decision_making_responsibility": 86},
        "technical": ["Branch P&L", "Team performance", "Operational risk", "Service recovery"],
        "responsibilities": ["run the branch numbers and the branch team", "own the operational risk in the building", "step in when a customer problem escalates"],
        "human": ["leading people", "answering for the outcome", "putting things right for a customer"],
    },
    {
        "id": "bank-operations-officer", "title": "Bank Operations Officer", "sub": "Banking", "soc": "43-4141", "quality": "close",
        "aliases": ["back office officer", "banking operations", "settlements officer", "clearing officer"],
        "mix": {"routine_task_percentage": 78, "human_interaction_intensity": 30, "decision_making_responsibility": 48},
        "technical": ["Payments and clearing", "Account maintenance", "Reconciliation", "Exception handling"],
        "responsibilities": ["process payments, clearing and account changes", "reconcile what the systems disagree about", "escalate the entries that do not balance"],
        "human": ["dealing with the cases that do not fit", "answering for the outcome", "keeping everyone informed"],
    },
    {
        "id": "aml-analyst", "title": "AML and Compliance Analyst", "sub": "Banking", "soc": "13-1041", "quality": "direct",
        "aliases": ["anti-money laundering analyst", "kyc analyst", "financial crime analyst", "compliance analyst"],
        "mix": {"routine_task_percentage": 60, "human_interaction_intensity": 36, "decision_making_responsibility": 80, "regulatory_safety_sensitivity": 94},
        "technical": ["Transaction monitoring", "KYC and due diligence", "Suspicious activity reporting", "Sanctions screening"],
        "responsibilities": ["review alerts and decide which are real", "run know-your-customer checks on new accounts", "file the reports the regulator requires"],
        "human": ["knowing the right thing to do", "answering for the outcome", "questioning what looks true"],
    },
    {
        "id": "credit-risk-analyst", "title": "Credit Risk Analyst", "sub": "Banking", "soc": "13-2054", "quality": "direct",
        "aliases": ["risk analyst", "portfolio risk analyst", "provisioning analyst", "IFRS 9 analyst"],
        "mix": {"routine_task_percentage": 55, "human_interaction_intensity": 34, "decision_making_responsibility": 78},
        "technical": ["Portfolio modelling", "IFRS 9 provisioning", "Stress testing", "Risk reporting"],
        "responsibilities": ["model how a loan book behaves under stress", "set and defend provisioning numbers", "explain risk to people who must act on it"],
        "human": ["experienced judgement", "questioning what looks true", "explaining your work to other teams"],
    },
    {
        "id": "treasury-dealer", "title": "Treasury and FX Dealer", "sub": "Banking", "soc": "41-3031", "quality": "close",
        "aliases": ["forex dealer", "treasury officer", "money market dealer", "fx trader"],
        "mix": {"routine_task_percentage": 45, "human_interaction_intensity": 62, "decision_making_responsibility": 84},
        "technical": ["FX and money markets", "Position and limit management", "Pricing", "Liquidity management"],
        "responsibilities": ["price and place foreign exchange and money-market deals", "keep positions inside the limits", "read the market and move before it does"],
        "human": ["making the call in a crisis", "negotiating", "answering for the outcome"],
    },
    {
        "id": "investment-banker", "title": "Investment Banking Analyst", "sub": "Investment", "soc": "13-2051", "quality": "close",
        "aliases": ["corporate finance analyst", "m&a analyst", "transaction advisory"],
        "mix": {"routine_task_percentage": 58, "human_interaction_intensity": 56, "decision_making_responsibility": 66},
        "technical": ["Valuation modelling", "Due diligence", "Pitch material", "Deal structuring"],
        "responsibilities": ["build the model behind a deal", "run due diligence on what a business claims", "put the case to investors and boards"],
        "human": ["experienced judgement", "explaining your work to other teams", "negotiating"],
    },
    {
        "id": "wealth-manager", "title": "Wealth Manager", "sub": "Investment", "soc": "13-2052", "quality": "direct",
        "aliases": ["financial adviser", "investment adviser", "private banker", "portfolio adviser"],
        "mix": {"routine_task_percentage": 40, "human_interaction_intensity": 86, "decision_making_responsibility": 74},
        "technical": ["Portfolio construction", "Risk profiling", "Tax and estate basics", "Suitability documentation"],
        "responsibilities": ["understand what a client is actually saving for", "build and rebalance a portfolio to match", "hold clients steady when markets move"],
        "human": ["being trusted with private matters", "knowing the right thing to do", "reading people"],
    },
    {
        "id": "microfinance-officer", "title": "Microfinance Officer", "sub": "Microfinance", "soc": "13-2072", "quality": "analogue",
        "aliases": ["mfi loan officer", "group lending officer", "field credit officer", "chama officer"],
        "mix": {"routine_task_percentage": 52, "human_interaction_intensity": 90, "physical_world_requirement": 66, "decision_making_responsibility": 60},
        "technical": ["Group lending", "Field appraisal", "Repayment discipline", "Cash handling in the field"],
        "responsibilities": ["appraise borrowers who have no formal records", "hold group meetings and keep repayment on track", "know the market and the people in it"],
        "human": ["being trusted locally", "reading people", "relationships with suppliers and the community"],
    },
    {
        "id": "sacco-officer", "title": "SACCO Officer", "sub": "Cooperative Finance", "soc": "13-2072", "quality": "analogue",
        "aliases": ["sacco loans officer", "cooperative officer", "credit union officer", "member services officer"],
        "mix": {"routine_task_percentage": 58, "human_interaction_intensity": 82, "decision_making_responsibility": 58},
        "technical": ["Member lending rules", "Share and deposit records", "Cooperative regulation", "Dividend computation"],
        "responsibilities": ["assess member loans against the cooperative's own rules", "keep share, deposit and guarantee records straight", "explain decisions to a membership that owns the institution"],
        "human": ["being trusted locally", "keeping everyone informed", "knowing the right thing to do"],
    },
    {
        "id": "mobile-money-officer", "title": "Agency and Mobile Money Officer", "sub": "Digital Finance", "soc": "43-3071", "quality": "analogue",
        "aliases": ["agency banking officer", "mobile money officer", "digital channels officer", "agent network officer"],
        "mix": {"routine_task_percentage": 66, "human_interaction_intensity": 72, "decision_making_responsibility": 52},
        "technical": ["Agent onboarding", "Float and liquidity management", "Fraud patterns", "Channel troubleshooting"],
        "responsibilities": ["recruit and support the agent network", "keep float and liquidity available where it is needed", "spot fraud patterns in transaction data"],
        "human": ["being trusted locally", "putting things right for a customer", "dealing with the cases that do not fit"],
    },
    {
        "id": "mortgage-officer", "title": "Mortgage Officer", "sub": "Banking", "soc": "13-2072", "quality": "close",
        "aliases": ["home loans officer", "property finance officer", "mortgage adviser"],
        "mix": {"routine_task_percentage": 60, "human_interaction_intensity": 72, "decision_making_responsibility": 64},
        "technical": ["Property valuation review", "Title and security checks", "Long-term affordability", "Legal documentation"],
        "responsibilities": ["assess whether a buyer can carry a twenty-year loan", "check title, valuation and security documents", "walk buyers through the longest financial decision of their life"],
        "human": ["being trusted with private matters", "keeping everyone informed", "experienced judgement"],
    },
    {
        "id": "bancassurance-officer", "title": "Bancassurance Officer", "sub": "Banking", "soc": "41-3021", "quality": "close",
        "aliases": ["bank insurance officer", "insurance sales officer", "assurance officer"],
        "mix": {"routine_task_percentage": 56, "human_interaction_intensity": 84, "decision_making_responsibility": 54},
        "technical": ["Insurance product knowledge", "Needs-based selling", "Claims support", "Cross-sell analytics"],
        "responsibilities": ["match insurance cover to what a banking customer actually risks", "support customers through claims", "work the bank's customer base without abusing it"],
        "human": ["being trusted with private matters", "reading people", "putting things right for a customer"],
    },
]


def main() -> int:
    payload = json.loads(CAREERS.read_text(encoding="utf-8"))
    crosswalk = json.loads(CROSSWALK.read_text(encoding="utf-8"))
    existing = {career["id"] for career in payload["careers"]}
    template = next(c for c in payload["careers"] if c["id"] == "bank-teller")

    added = 0
    for spec in NEW_CAREERS:
        if spec["id"] in existing:
            continue
        career = deepcopy(template)
        career.update({
            "id": spec["id"],
            "canonical_title": spec["title"],
            "alternative_titles": spec["aliases"],
            "sub_industry": spec["sub"],
            "typical_responsibilities": spec["responsibilities"],
            "core_human_skills": spec["human"],
            "technical_skills": spec["technical"],
            "ai_exposure": 0,
            "ai_augmentation_potential": 0,
            "search_tags": sorted({
                *[t.lower() for t in spec["aliases"]],
                spec["title"].lower(), spec["sub"].lower(), "bank", "banking", "finance",
            }),
            "roadmap_slug": None,
        })
        career.update(spec["mix"])
        career["evidence"] = {"coverage": "fallback", "method": "pending evidence build", "sources": [], "last_reviewed": ""}
        payload["careers"].append(career)
        crosswalk["careers"][spec["id"]] = [spec["soc"], spec["quality"]]
        added += 1

    if not added:
        print("nothing to add - all banking careers already present")
        return 0

    payload["careers"].sort(key=lambda c: (c["industry"], c["canonical_title"]))
    CAREERS.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    CROSSWALK.write_text(json.dumps(crosswalk, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"added {added} banking careers ({len(payload['careers'])} total)")
    print("now run: python scripts/build_career_evidence.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
