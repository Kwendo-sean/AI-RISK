"""
Will AI Take My Job? — Skill Combat Backend (Friend 2's engine)
Run alongside main.py on a different port, or import into main.py.
uvicorn game_backend_v2:app --reload --port 8001
"""

from fastapi import FastAPI, HTTPException, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Literal, Optional
import random, uuid

router = APIRouter()

AI_WEAPONS = [
    {"id":"claude","name":"Claude / Claude Code","xp":350,"category":"AI Assistant","icon":"brain","description":"Advanced AI assistant for writing, analysis, research and reasoning.","skill_tags":["documentation","reporting","writing","research","analysis","communication","drafting","summarising","advisory","compliance","report","narrative"],"career_tags":["lawyer","journalist","teacher","nurse","social_worker","ngo_officer","policy_analyst","hr_manager","marketing_manager","pr_specialist","copywriter","education_officer"],"why":"Drafts reports, letters, case notes, lesson plans, and legal documents in seconds."},
    {"id":"chatgpt","name":"ChatGPT","xp":300,"category":"AI Assistant","icon":"message","description":"Versatile AI assistant for writing, brainstorming and problem-solving.","skill_tags":["writing","drafting","communication","research","documentation","planning","scheduling","reporting"],"career_tags":["teacher","journalist","lawyer","social_worker","hr_manager","marketing_manager","office_admin"],"why":"Handles first drafts, summaries, and communication — saving hours per week."},
    {"id":"perplexity","name":"Perplexity AI","xp":220,"category":"AI Assistant","icon":"search","description":"AI-powered search and research with cited sources.","skill_tags":["research","fact-checking","verification","analysis","market analysis","policy research","legal research","literature review","sourcing"],"career_tags":["journalist","lawyer","policy_analyst","researcher","economist","ngo_officer","teacher","scientist"],"why":"Replaces hours of manual research — gives cited, current answers instantly."},
    {"id":"gemini","name":"Google Gemini","xp":200,"category":"AI Assistant","icon":"sparkle","description":"Multimodal Google AI — works with text, images, and documents.","skill_tags":["documentation","analysis","writing","scheduling","data entry","summarising","report generation"],"career_tags":["teacher","office_admin","nurse","social_worker","hr_manager","civil_servant"],"why":"Integrates with Google Workspace — automates docs, emails and scheduling."},
    {"id":"n8n","name":"n8n","xp":340,"category":"Automation","icon":"zap","description":"Open-source visual automation — connect any app, automate any workflow.","skill_tags":["data entry","scheduling","routine documentation","report generation","filing","administrative tasks","payroll processing","invoice","manual scheduling","repetitive tasks","handover reporting"],"career_tags":["accountant","office_admin","hr_manager","supply_chain","procurement_officer","logistics_coordinator","nurse","teacher","civil_servant","compliance_officer"],"why":"Automates your repetitive tasks — data entry, reports, scheduling — without coding."},
    {"id":"make","name":"Make (Integromat)","xp":300,"category":"Automation","icon":"link","description":"No-code workflow builder — automate between 1,000+ apps.","skill_tags":["data entry","invoice","scheduling","reporting","administrative tasks","filing","routine documentation","payroll","social media scheduling"],"career_tags":["accountant","office_admin","marketing_manager","social_media_manager","hr_manager","journalist","copywriter","graphic_designer"],"why":"Connects your tools and eliminates manual copy-paste work between systems."},
    {"id":"zapier","name":"Zapier","xp":240,"category":"Automation","icon":"plug","description":"Beginner-friendly automation — if this, then that.","skill_tags":["scheduling","data entry","filing","routine documentation","social media scheduling","administrative tasks","email management"],"career_tags":["office_admin","marketing_manager","social_media_manager","pr_specialist","journalist","teacher","hr_manager"],"why":"Easiest automation tool — set up in minutes, no technical skills needed."},
    {"id":"notion_ai","name":"Notion AI","xp":200,"category":"Automation","icon":"note","description":"AI-powered workspace for notes, docs, and team knowledge.","skill_tags":["documentation","planning","reporting","scheduling","knowledge management","drafting","project management","record keeping","writing"],"career_tags":["teacher","journalist","ngo_officer","policy_analyst","hr_manager","marketing_manager","social_worker"],"why":"Centralises notes, plans, and reports — AI writes first drafts for you."},
    {"id":"airtable_ai","name":"Airtable AI","xp":200,"category":"Automation","icon":"table","description":"Smart database with AI — tracks clients, cases, inventory, and projects.","skill_tags":["record keeping","data entry","inventory management","case management","client tracking","scheduling","budget tracking","compliance tracking"],"career_tags":["social_worker","ngo_officer","nurse","lawyer","hr_manager","supply_chain","procurement_officer","teacher","compliance_officer"],"why":"Replaces messy spreadsheets — tracks cases, clients, and records with AI."},
    {"id":"ms_copilot","name":"Microsoft Copilot","xp":180,"category":"Automation","icon":"windows","description":"AI across Word, Excel, Outlook, and Teams — for Office users.","skill_tags":["report generation","data entry","documentation","spreadsheet maintenance","scheduling","email drafting","payroll processing","invoice"],"career_tags":["accountant","office_admin","hr_manager","civil_servant","lawyer","auditor","compliance_officer","supply_chain"],"why":"If you use Microsoft Office, Copilot automates your most time-consuming tasks."},
    {"id":"canva_ai","name":"Canva AI","xp":220,"category":"Design & Content","icon":"palette","description":"AI-powered design — create graphics, presentations, and social content.","skill_tags":["visual design","presentation","social media content","template design","marketing materials","brand materials","infographics","report design"],"career_tags":["teacher","social_media_manager","marketing_manager","journalist","ngo_officer","pr_specialist","graphic_designer","copywriter","event_planner"],"why":"Create professional-quality visuals in minutes — no design training needed."},
    {"id":"adobe_firefly","name":"Adobe Firefly","xp":200,"category":"Design & Content","icon":"fire","description":"Professional AI image generation — fully licensed for commercial use.","skill_tags":["image creation","visual design","brand visuals","marketing materials","retouching","concept visuals"],"career_tags":["graphic_designer","marketing_manager","journalist","pr_specialist","social_media_manager","copywriter"],"why":"Generate commercial-quality images instantly — licensed and safe to use."},
    {"id":"midjourney","name":"Midjourney","xp":240,"category":"Design & Content","icon":"image","description":"High-quality AI art and image generation via Discord.","skill_tags":["visual concept","image creation","brand visuals","creative direction","concept art"],"career_tags":["graphic_designer","journalist","marketing_manager","creator","animator"],"why":"Turn a text prompt into a stunning image — for campaigns, concepts, and content."},
    {"id":"gamma","name":"Gamma","xp":180,"category":"Design & Content","icon":"slides","description":"AI-generated presentations, documents, and web pages.","skill_tags":["presentation","reporting","documentation","proposal writing","grant writing","training materials","lesson plans"],"career_tags":["teacher","ngo_officer","policy_analyst","lawyer","marketing_manager","social_worker","hr_manager","journalist"],"why":"Creates polished presentations and reports from a prompt — in under 2 minutes."},
    {"id":"heygen","name":"HeyGen","xp":260,"category":"Video & Voice","icon":"video","description":"AI avatar video creation — create professional videos without a camera.","skill_tags":["video content","training materials","client communication","explainer content","presentations","awareness campaigns"],"career_tags":["teacher","social_media_manager","marketing_manager","ngo_officer","journalist","hr_manager","public_health","community_dev"],"why":"Create professional training and awareness videos without any filming."},
    {"id":"runway_ml","name":"Runway ML","xp":280,"category":"Video & Voice","icon":"film","description":"AI video generation and editing — text-to-video and smart editing.","skill_tags":["video production","content creation","social media content","visual storytelling","documentary"],"career_tags":["journalist","social_media_manager","videographer","graphic_designer","marketing_manager","creator"],"why":"Generate and edit video content from text — no camera or editing skills needed."},
    {"id":"elevenlabs","name":"ElevenLabs","xp":240,"category":"Video & Voice","icon":"mic","description":"AI voice cloning and synthesis — create natural-sounding audio.","skill_tags":["audio content","training materials","public communication","accessibility","broadcasting","community outreach"],"career_tags":["journalist","teacher","social_worker","public_health","community_dev","ngo_officer","religious_leader"],"why":"Create professional audio content and voiceovers in any language — instantly."},
    {"id":"descript","name":"Descript","xp":200,"category":"Video & Voice","icon":"scissors","description":"AI audio and video editing — edit media by editing text.","skill_tags":["audio editing","video editing","transcription","interview recording","podcast production","meeting notes"],"career_tags":["journalist","social_media_manager","teacher","hr_manager","ngo_officer","videographer"],"why":"Edit audio and video as easily as editing a Word document — no technical skills needed."},
    {"id":"otter_ai","name":"Otter.ai","xp":180,"category":"Video & Voice","icon":"mic2","description":"AI transcription and meeting notes — never manually type notes again.","skill_tags":["meeting notes","documentation","interview transcription","clinical documentation","case notes","record keeping","shift handover","reporting"],"career_tags":["nurse","social_worker","lawyer","journalist","hr_manager","ngo_officer","teacher","doctor","clinical_officer","psychologist"],"why":"Transcribes meetings, interviews, and consultations automatically — no note-taking."},
    {"id":"loom_ai","name":"Loom AI","xp":160,"category":"Video & Voice","icon":"camera","description":"AI-enhanced video messaging — record, send, and summarise video messages.","skill_tags":["client communication","team communication","training delivery","stakeholder updates","feedback"],"career_tags":["teacher","hr_manager","social_worker","ngo_officer","marketing_manager","event_planner"],"why":"Replace long emails with short videos — AI adds transcripts and action items."},
    {"id":"jasper_ai","name":"Jasper AI","xp":180,"category":"Writing & Research","icon":"pen","description":"AI copywriting for marketing — brand-consistent content at scale.","skill_tags":["copywriting","marketing content","social media content","email campaigns","blog writing","ad copy","brand writing"],"career_tags":["marketing_manager","social_media_manager","copywriter","pr_specialist","journalist","ngo_officer"],"why":"Writes marketing copy, ads, and social content in your brand voice — instantly."},
    {"id":"copy_ai","name":"Copy.ai","xp":160,"category":"Writing & Research","icon":"copy","description":"AI-generated marketing copy — quick content for any use case.","skill_tags":["copywriting","social media content","email drafting","marketing materials","press releases","proposals"],"career_tags":["marketing_manager","social_media_manager","copywriter","journalist","pr_specialist","travel_agent"],"why":"Generate professional copy for any platform in seconds — with no writer's block."},
    {"id":"tome","name":"Tome","xp":160,"category":"Writing & Research","icon":"book","description":"AI storytelling and narrative documents — for pitches and proposals.","skill_tags":["proposal writing","storytelling","narrative","grant writing","pitch decks","case studies"],"career_tags":["ngo_officer","journalist","lawyer","marketing_manager","social_worker","policy_analyst"],"why":"Turns your ideas into compelling, professionally structured narratives."},
    {"id":"pal_future_skills","name":"PAL Future Skills Course","xp":500,"category":"PAL Course","icon":"star","description":"Kenya-focused AI upskilling — learn to work alongside AI in your career.","skill_tags":["ai literacy","digital skills","future readiness","upskilling","career transition","automation awareness","data entry","routine documentation","repetitive tasks","scheduling","reporting","administrative tasks"],"career_tags":["*"],"why":"The most direct path to future-proofing your career in the Kenyan job market."},
    {"id":"pal_data_analytics","name":"PAL Data Analytics Course","xp":500,"category":"PAL Course","icon":"chart","description":"Kenya Labour Market data skills — analyse data to make better decisions.","skill_tags":["data analysis","reporting","statistical analysis","research","evidence-based decision making","spreadsheet","record keeping","financial analysis","market analysis"],"career_tags":["accountant","economist","social_worker","ngo_officer","policy_analyst","nurse","teacher","journalist","hr_manager","civil_servant","agronomist"],"why":"Data literacy is the #1 skill protecting Kenyan workers from automation."},
]

CAREER_SKILLS = {
    "nurse":{"label":"Registered Nurse","risk":15,"skills":[{"name":"Empathetic Communication","type":"human","power":22},{"name":"Emergency Patient Triage","type":"analytical","power":17},{"name":"Patient Advocacy","type":"human","power":20},{"name":"Care Team Coordination","type":"human","power":18},{"name":"Ethical Medical Decision-Making","type":"human","power":21},{"name":"Clinical Diagnostic Reasoning","type":"analytical","power":16},{"name":"Procedural Expertise","type":"technical","power":14},{"name":"Shift Handover Reporting","type":"routine","power":13},{"name":"Routine EHR Documentation","type":"routine","power":12}]},
    "gp":{"label":"General Practitioner","risk":12,"skills":[{"name":"Patient-Centred Consultation","type":"human","power":23},{"name":"Clinical Diagnostic Reasoning","type":"analytical","power":20},{"name":"Chronic Disease Management","type":"analytical","power":18},{"name":"Community Health Leadership","type":"human","power":19},{"name":"Preventive Care Advisory","type":"human","power":17},{"name":"Referral Judgement","type":"analytical","power":16},{"name":"Basic Record Entry","type":"routine","power":12},{"name":"Prescription Documentation","type":"routine","power":11}]},
    "mental_health":{"label":"Mental Health Counsellor","risk":10,"skills":[{"name":"Therapeutic Relationship Building","type":"human","power":24},{"name":"Trauma-Informed Care","type":"human","power":23},{"name":"Crisis Intervention","type":"human","power":22},{"name":"Cultural Competence","type":"human","power":20},{"name":"Treatment Planning","type":"analytical","power":18},{"name":"Suicide Risk Assessment","type":"analytical","power":17},{"name":"Session Note Writing","type":"routine","power":12},{"name":"Case File Management","type":"routine","power":11}]},
    "social_worker":{"label":"Social Worker","risk":18,"skills":[{"name":"Trauma-Informed Case Management","type":"human","power":23},{"name":"Community Trust Building","type":"human","power":21},{"name":"Conflict Resolution","type":"human","power":20},{"name":"Cultural Mediation","type":"human","power":19},{"name":"Crisis Intervention","type":"analytical","power":17},{"name":"Programme Impact Assessment","type":"analytical","power":16},{"name":"Case File Administration","type":"routine","power":12},{"name":"Standard Report Writing","type":"routine","power":11}]},
    "primary_teacher":{"label":"Primary School Teacher","risk":22,"skills":[{"name":"Adaptive & Inclusive Instruction","type":"human","power":22},{"name":"Student Welfare Mentorship","type":"human","power":21},{"name":"Behavioural Management","type":"human","power":19},{"name":"Creative Facilitation","type":"human","power":18},{"name":"Curriculum Localisation","type":"analytical","power":16},{"name":"Parent Engagement","type":"human","power":17},{"name":"Grade Entry & Reporting","type":"routine","power":12},{"name":"Attendance Record Management","type":"routine","power":10}]},
    "secondary_teacher":{"label":"Secondary School Teacher","risk":25,"skills":[{"name":"Subject Mastery & Explanation","type":"human","power":21},{"name":"Student Mentorship","type":"human","power":20},{"name":"Exam Coaching","type":"analytical","power":17},{"name":"Community Trust","type":"human","power":18},{"name":"Curriculum Design","type":"analytical","power":16},{"name":"Co-curricular Leadership","type":"human","power":15},{"name":"Grade Entry & Reporting","type":"routine","power":12},{"name":"Printing & Filing Materials","type":"routine","power":10}]},
    "accountant":{"label":"Accountant","risk":79,"skills":[{"name":"Strategic Financial Judgement","type":"human","power":20},{"name":"Client Relationship Management","type":"human","power":19},{"name":"Ethical Advisory","type":"human","power":18},{"name":"Complex Regulatory Interpretation","type":"analytical","power":17},{"name":"Audit Oversight","type":"analytical","power":16},{"name":"Financial Forecasting","type":"analytical","power":15},{"name":"Bookkeeping & Reconciliation","type":"routine","power":17},{"name":"Payroll Processing","type":"routine","power":16},{"name":"Invoice Data Entry","type":"routine","power":15},{"name":"Spreadsheet Maintenance","type":"routine","power":14}]},
    "hr_manager":{"label":"HR Manager","risk":55,"skills":[{"name":"Conflict Mediation","type":"human","power":21},{"name":"Talent Judgement","type":"human","power":20},{"name":"Leadership Coaching","type":"human","power":19},{"name":"Organisational Culture Design","type":"human","power":18},{"name":"Employment Law Interpretation","type":"analytical","power":17},{"name":"Change Management","type":"analytical","power":16},{"name":"Payroll Administration","type":"routine","power":14},{"name":"Leave Record Management","type":"routine","power":12},{"name":"Standard Contract Generation","type":"routine","power":13}]},
    "marketing_manager":{"label":"Marketing Manager","risk":52,"skills":[{"name":"Brand Strategy","type":"human","power":20},{"name":"Consumer Insight Interpretation","type":"analytical","power":18},{"name":"Creative Direction","type":"human","power":19},{"name":"Agency Management","type":"human","power":17},{"name":"Campaign P&L Management","type":"analytical","power":16},{"name":"Social Media Scheduling","type":"routine","power":13},{"name":"Report Generation","type":"routine","power":12},{"name":"Template Content Resizing","type":"routine","power":11}]},
    "office_admin":{"label":"Office Administrator","risk":80,"skills":[{"name":"Executive Support & Judgement","type":"human","power":19},{"name":"Crisis Scheduling","type":"human","power":18},{"name":"Stakeholder Coordination","type":"human","power":17},{"name":"Event Logistics","type":"analytical","power":15},{"name":"Multi-task Prioritisation","type":"analytical","power":14},{"name":"Data Entry & Filing","type":"routine","power":17},{"name":"Email Management","type":"routine","power":16},{"name":"Scheduling & Calendar Management","type":"routine","power":15},{"name":"Invoice Processing","type":"routine","power":14}]},
    "customer_service":{"label":"Customer Service Agent","risk":85,"skills":[{"name":"Empathy Under Pressure","type":"human","power":22},{"name":"Complex Complaint Resolution","type":"human","power":21},{"name":"Customer Retention","type":"human","power":20},{"name":"Cultural Sensitivity","type":"human","power":18},{"name":"Escalation Judgement","type":"analytical","power":16},{"name":"Ticket Logging & Updates","type":"routine","power":16},{"name":"FAQ Documentation","type":"routine","power":14},{"name":"Standard Response Templates","type":"routine","power":15}]},
    "lawyer":{"label":"Lawyer","risk":35,"skills":[{"name":"Legal Reasoning & Argumentation","type":"human","power":23},{"name":"Client Advocacy","type":"human","power":22},{"name":"Courtroom Strategy","type":"human","power":21},{"name":"Negotiation & Mediation","type":"human","power":20},{"name":"Ethical Judgement","type":"human","power":19},{"name":"Legal Research & Analysis","type":"analytical","power":17},{"name":"Regulatory Interpretation","type":"analytical","power":16},{"name":"Document Review","type":"routine","power":16},{"name":"Contract Template Population","type":"routine","power":14}]},
    "journalist":{"label":"Journalist","risk":55,"skills":[{"name":"Investigative Source Cultivation","type":"human","power":22},{"name":"Narrative Framing","type":"human","power":21},{"name":"Editorial Judgement","type":"human","power":20},{"name":"Accountability Journalism","type":"human","power":19},{"name":"Audience Strategy","type":"analytical","power":16},{"name":"Fact-Checking & Verification","type":"analytical","power":15},{"name":"SEO Article Writing","type":"routine","power":15},{"name":"Press Release Summarisation","type":"routine","power":13},{"name":"Social Media Scheduling","type":"routine","power":11}]},
    "graphic_designer":{"label":"Graphic Designer","risk":58,"skills":[{"name":"Creative Direction","type":"human","power":21},{"name":"Brand Strategy","type":"human","power":20},{"name":"Client Relationship","type":"human","power":19},{"name":"Conceptual Thinking","type":"human","power":18},{"name":"Art Direction","type":"human","power":17},{"name":"Typography Mastery","type":"technical","power":15},{"name":"Template Resizing","type":"routine","power":14},{"name":"Asset Export & Packaging","type":"routine","power":12},{"name":"Routine Social Media Sizing","type":"routine","power":13}]},
    "social_media_manager":{"label":"Social Media Manager","risk":65,"skills":[{"name":"Community Voice & Culture","type":"human","power":21},{"name":"Crisis Communication","type":"human","power":20},{"name":"Influencer Relationship Mgmt","type":"human","power":19},{"name":"Brand Protection","type":"human","power":18},{"name":"Platform Strategy","type":"analytical","power":17},{"name":"Post Scheduling","type":"routine","power":15},{"name":"Analytics Report Generation","type":"routine","power":13},{"name":"Template Content Resizing","type":"routine","power":12}]},
    "ngo_officer":{"label":"NGO Programme Officer","risk":35,"skills":[{"name":"Programme Design & M&E","type":"analytical","power":18},{"name":"Stakeholder Engagement","type":"human","power":21},{"name":"Community Mobilisation","type":"human","power":20},{"name":"Advocacy & Policy Influencing","type":"human","power":19},{"name":"Grant Writing","type":"technical","power":16},{"name":"Donor Reporting","type":"technical","power":15},{"name":"Routine Data Collection","type":"routine","power":13},{"name":"Standard Progress Reporting","type":"routine","power":12}]},
    "chef":{"label":"Chef","risk":35,"skills":[{"name":"Culinary Creativity & Technique","type":"human","power":22},{"name":"Kitchen Leadership","type":"human","power":20},{"name":"Cultural Food Adaptation","type":"human","power":19},{"name":"Menu Engineering","type":"analytical","power":17},{"name":"Cost Control","type":"analytical","power":15},{"name":"Basic Stock Entry","type":"routine","power":11},{"name":"Standard Recipe Documentation","type":"routine","power":10}]},
    "tour_guide":{"label":"Tour Guide","risk":22,"skills":[{"name":"Cultural Storytelling","type":"human","power":23},{"name":"Guest Psychology","type":"human","power":21},{"name":"Emergency Response","type":"human","power":20},{"name":"Local Knowledge","type":"human","power":22},{"name":"Language Facilitation","type":"human","power":19},{"name":"Itinerary Adaptation","type":"analytical","power":16},{"name":"Booking Record Entry","type":"routine","power":10}]},
    "market_trader":{"label":"Market Trader","risk":60,"skills":[{"name":"Market Price Intelligence","type":"analytical","power":18},{"name":"Customer Relationship","type":"human","power":21},{"name":"Community Network","type":"human","power":20},{"name":"Supplier Negotiation","type":"human","power":19},{"name":"Stock Judgement","type":"analytical","power":16},{"name":"Manual Stock Entry","type":"routine","power":13},{"name":"Daily Sales Recording","type":"routine","power":12}]},
    "mpesa_agent":{"label":"M-Pesa Agent","risk":88,"skills":[{"name":"Customer Trust & Relationship","type":"human","power":22},{"name":"Fraud Detection Instinct","type":"human","power":21},{"name":"Community Problem-Solving","type":"human","power":20},{"name":"Cash Liquidity Management","type":"analytical","power":16},{"name":"Business Management","type":"analytical","power":15},{"name":"Manual Transaction Recording","type":"routine","power":16},{"name":"Daily Float Reconciliation","type":"routine","power":15},{"name":"Standard Register Entry","type":"routine","power":14}]},
    "farm_manager":{"label":"Farm Manager","risk":48,"skills":[{"name":"Farm Operations Planning","type":"analytical","power":18},{"name":"Staff Management","type":"human","power":20},{"name":"Market Linkage","type":"human","power":19},{"name":"Supply Chain Coordination","type":"analytical","power":16},{"name":"Budget & Cost Control","type":"analytical","power":15},{"name":"Equipment Maintenance","type":"technical","power":14},{"name":"Routine Record Keeping","type":"routine","power":12},{"name":"Standard Harvest Reports","type":"routine","power":11}]},
}

AVATARS = {
    "caretaker":{"label":"The Caretaker","bonus_type":"human","bonus_multiplier":1.25},
    "analyst":{"label":"The Analyst","bias":["analytical"],"bonus_type":"analytical","bonus_multiplier":1.30},
    "builder":{"label":"The Builder","bias":["technical"],"bonus_type":"technical","bonus_multiplier":1.30},
    "strategist":{"label":"The Strategist","bias":["analytical","human"],"bonus_type":"analytical","bonus_multiplier":1.20},
    "creator":{"label":"The Creator","bias":["human"],"bonus_type":"human","bonus_multiplier":1.35},
    "pioneer":{"label":"The Pioneer","bias":["technical","analytical"],"bonus_type":"technical","bonus_multiplier":1.25},
}

SKILL_TYPE_META = {
    "human":{"color":"#27AE60","label":"Human Edge","effect":"damage_ai","icon":"sword"},
    "analytical":{"color":"#F39C12","label":"Analytical","effect":"split","icon":"bolt"},
    "technical":{"color":"#3498DB","label":"Technical","effect":"split_light","icon":"wrench"},
    "routine":{"color":"#E74C3C","label":"Automatable","effect":"damage_player","icon":"warning"},
}

sessions: dict = {}

_SECTOR_FALLBACK = {
    "agriculture":"farm_manager","food":"chef","healthcare":"nurse","health":"nurse",
    "medical":"gp","mental":"mental_health","social":"social_worker","education":"primary_teacher",
    "teacher":"primary_teacher","school":"primary_teacher","finance":"accountant",
    "accounting":"accountant","bank":"accountant","audit":"accountant","business":"hr_manager",
    "admin":"office_admin","office":"office_admin","customer":"customer_service",
    "legal":"lawyer","law":"lawyer","media":"journalist","journalism":"journalist",
    "design":"graphic_designer","creative":"graphic_designer","marketing":"marketing_manager",
    "digital":"social_media_manager","ngo":"ngo_officer","community":"ngo_officer",
    "tourism":"tour_guide","hospitality":"chef","retail":"market_trader","trade":"market_trader",
    "it":"office_admin","tech":"office_admin","engineering":"office_admin",
}

def _resolve_career_key(raw:str)->str:
    key=raw.lower().strip().replace(" ","_").replace("-","_")
    if key in CAREER_SKILLS: return key
    for k in CAREER_SKILLS:
        if k in key or key in k: return k
    for word, fallback in _SECTOR_FALLBACK.items():
        if word in key: return fallback
    return "office_admin"

def build_deck(career_key:str,avatar_key:str)->list:
    career=CAREER_SKILLS[career_key]
    avatar=AVATARS.get(avatar_key,AVATARS["caretaker"])
    by_type:dict={"human":[],"analytical":[],"technical":[],"routine":[]}
    for skill in career["skills"]:
        s=dict(skill)
        if s["type"]==avatar.get("bonus_type"):
            s["power"]=int(s["power"]*avatar.get("bonus_multiplier",1.0))
        by_type[s["type"]].append(s)
    bias=avatar.get("bias",["human"])
    strong_pool=[s for t in bias for s in by_type.get(t,[])]
    used={s["name"] for s in strong_pool}
    medium_pool=[s for s in by_type.get("analytical",[])+by_type.get("technical",[]) if s["name"] not in used]
    weak_pool=by_type.get("routine",[])
    def pick(p,n): return random.sample(p,min(n,len(p)))
    chosen=pick(strong_pool,3)+pick(medium_pool,2)+pick(weak_pool,2)
    if len(chosen)<7:
        used2={c["name"] for c in chosen}
        rem=[s for pool in by_type.values() for s in pool if s["name"] not in used2]
        chosen+=random.sample(rem,min(7-len(chosen),len(rem)))
    random.shuffle(chosen)
    deck=[]
    flavours={"human":["Machines can process data — they cannot truly care.","Human connection is your permanent competitive moat."],"analytical":["AI augments you here — but the judgement is still yours.","The insight is human. The tools are AI."],"technical":["You and AI are co-pilots on this one.","Adapt this skill to AI or watch it erode."],"routine":["AI was built for exactly this task. Be careful.","Repetition is the enemy of job security."]}
    for s in chosen:
        meta=SKILL_TYPE_META[s["type"]]
        deck.append({"id":str(uuid.uuid4())[:8],"name":s["name"],"type":s["type"],"type_label":meta["label"],"color":meta["color"],"icon":meta["icon"],"power":s["power"],"effect":meta["effect"],"flavour":random.choice(flavours[s["type"]])})
    return deck

def resolve_damage(card:dict,player_hp:float,ai_hp:float,answer:str)->tuple:
    power=card["power"]
    if answer=="dont_have":
        penalty=int(power*0.8)
        return round(max(player_hp-penalty,15.0),1),round(ai_hp,1),f"Gap exposed! AI exploits '{card['name']}' — you lose {penalty} HP."
    effect=card["effect"]
    if effect=="damage_ai":
        return round(player_hp,1),round(ai_hp-power,1),f"Human edge! '{card['name']}' deals {power} damage to AI."
    elif effect=="damage_player":
        penalty=int(power*0.6)
        return round(max(player_hp-penalty,15.0),1),round(ai_hp,1),f"'{card['name']}' is automatable — AI already does this. -{penalty} HP."
    elif effect=="split":
        ai_dmg=int(power*0.6);player_dmg=int(power*0.4)
        return round(max(player_hp-player_dmg,15.0),1),round(ai_hp-ai_dmg,1),f"Analytical trade-off: -{player_dmg} HP you, -{ai_dmg} HP AI."
    elif effect=="split_light":
        ai_dmg=int(power*0.5);player_dmg=int(power*0.3)
        return round(max(player_hp-player_dmg,15.0),1),round(ai_hp-ai_dmg,1),f"Co-pilot mode: -{player_dmg} HP you, -{ai_dmg} HP AI."
    return round(player_hp,1),round(ai_hp-power,1),f"Card played: {power} damage to AI."

def recommend_weapons(skill_gaps:list,career_key:str,max_results:int=6)->list:
    if not skill_gaps: return _default_weapons(career_key,max_results)
    gap_words={w for g in skill_gaps for w in g.lower().replace("-"," ").replace("&"," ").split() if len(w)>3}
    scored=[]
    pal=[]
    for tool in AI_WEAPONS:
        if tool["category"]=="PAL Course": pal.append(tool);continue
        score=0.0
        for tag in tool["skill_tags"]:
            tw=set(tag.lower().replace("-"," ").split());overlap=tw&gap_words
            score+=len(overlap)*2
            if tw.issubset(gap_words): score+=3
        if career_key in tool.get("career_tags",[]): score+=5
        if score>0: scored.append((score,tool))
    scored.sort(key=lambda x:-x[0])
    top=[t for _,t in scored[:max_results-1]]
    if pal:
        best=next((p for p in pal if career_key in p.get("career_tags",[]) or "*" in p.get("career_tags",[])),pal[0])
        top.append(best)
    return top if len(top)>1 else _default_weapons(career_key,max_results)

def _default_weapons(career_key:str,max_results:int)->list:
    scored=[(5 if career_key in t.get("career_tags",[]) else 0,t) for t in AI_WEAPONS if t["category"]!="PAL Course"]
    scored.sort(key=lambda x:-x[0])
    top=[t for _,t in scored[:max_results-1]]
    pal=next((t for t in AI_WEAPONS if t["category"]=="PAL Course" and "*" in t.get("career_tags",[])),None)
    if pal: top.append(pal)
    return top

class StartReq(BaseModel): career:str; avatar:str
class PlayReq(BaseModel): session_id:str; card_id:str; answer:Literal["have","dont_have"]
class WeaponReq(BaseModel): session_id:str; max_tools:Optional[int]=6

@router.get("/api/game/health")
def health(): return {"status":"ok","sessions":len(sessions),"careers":len(CAREER_SKILLS),"weapons":len(AI_WEAPONS)}

@router.get("/api/game/careers")
def list_careers(): return [{"key":k,"label":v["label"],"risk":v["risk"]} for k,v in CAREER_SKILLS.items()]

@router.post("/api/game/start")
def start_game(req:StartReq):
    ck=_resolve_career_key(req.career)
    ak=req.avatar.lower().strip()
    if ck not in CAREER_SKILLS: ck="office_admin"
    if ak not in AVATARS: ak="caretaker"
    career=CAREER_SKILLS[ck]; avatar=AVATARS[ak]
    deck=build_deck(ck,ak); sid=str(uuid.uuid4())
    sessions[sid]={"career_key":ck,"avatar_key":ak,"player_hp":100.0,"ai_hp":float(career["risk"]),"deck":{c["id"]:c for c in deck},"played":[],"skill_gaps":[],"round":0,"xp":0}
    return {"session_id":sid,"career":{"key":ck,"label":career["label"],"risk":career["risk"]},"avatar":{"key":ak,"label":avatar["label"]},"player_hp":100,"ai_hp":career["risk"],"cards":deck}

@router.post("/api/game/play-card")
def play_card(req:PlayReq):
    s=sessions.get(req.session_id)
    if not s: raise HTTPException(404,"Session not found")
    if req.card_id not in s["deck"]: raise HTTPException(400,"Card not found")
    card=s["deck"].pop(req.card_id)
    new_p,new_a,msg=resolve_damage(card,s["player_hp"],s["ai_hp"],req.answer)
    if req.answer=="dont_have": s["skill_gaps"].append(card["name"])
    xp=30 if card["type"]=="human" else 20 if card["type"]=="analytical" else 15 if card["type"]=="technical" else 5
    xp=xp if req.answer=="have" else 0
    s.update({"player_hp":new_p,"ai_hp":max(new_a,0),"round":s["round"]+1,"xp":s["xp"]+xp})
    remaining=len(s["deck"])
    status="ongoing"
    if new_a<=0: status="player_wins"
    elif remaining==0: status="player_wins" if new_p>max(new_a,0) else "round_over"
    return {"card":card,"answer":req.answer,"narrative":msg,"player_hp":new_p,"ai_hp":max(new_a,0),"round":s["round"],"cards_remaining":remaining,"xp_earned":xp,"total_xp":s["xp"],"status":status,"skill_gaps":s["skill_gaps"]}

@router.post("/api/game/equip-weapons")
def equip_weapons(req:WeaponReq):
    s=sessions.get(req.session_id)
    if not s: raise HTTPException(404,"Session not found")
    weapons=recommend_weapons(s["skill_gaps"],s["career_key"],min(req.max_tools or 6,8))
    career=CAREER_SKILLS[s["career_key"]]
    gaps=s["skill_gaps"]; gc=len(gaps)
    headline=(f"Outstanding! Mastered your {career['label']} skill set." if not gaps else f"{gc} gap{'s' if gc>1 else ''} found — time to level up.")
    return {"skill_gaps":gaps,"gap_count":gc,"headline":headline,"total_xp":s["xp"],"weapons":[{"id":w["id"],"name":w["name"],"xp":w["xp"],"category":w["category"],"icon":w["icon"],"description":w["description"],"why":w["why"]} for w in weapons]}

@router.get("/api/game/session/{session_id}")
def get_session(session_id:str):
    s=sessions.get(session_id)
    if not s: raise HTTPException(404,"Session not found")
    return {"session_id":session_id,"career_key":s["career_key"],"avatar_key":s["avatar_key"],"player_hp":s["player_hp"],"ai_hp":s["ai_hp"],"round":s["round"],"cards_remaining":len(s["deck"]),"skill_gaps":s["skill_gaps"],"xp":s["xp"]}

if __name__=="__main__":
    import uvicorn
    _app = FastAPI()
    _app.add_middleware(CORSMiddleware,allow_origins=["*"],allow_methods=["*"],allow_headers=["*"])
    _app.include_router(router)
    uvicorn.run(_app,host="0.0.0.0",port=8006,reload=False)