"""
Will AI Take My Job? — FastAPI Backend
Run: uvicorn main:app --reload --port 8000
"""

import os, json, asyncio, hashlib, time
from typing import Optional, AsyncGenerator
from contextlib import asynccontextmanager

import aiosqlite
try:  # optional: only needed for the legacy cloud scan, never on an offline box
    import anthropic
except ImportError:  # pragma: no cover - exercised on the Raspberry Pi build
    anthropic = None
import httpx
from fastapi import FastAPI, Query, Path, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr, Field
from dotenv import load_dotenv

from careers_data import CAREERS, SECTOR_THREATS, SECTOR_SKILLS
from gamebackendv2 import router as game_router
from platform_api import router as platform_router, SecurityAndOperationsMiddleware
from platform_content import validate_content
from platform_db import close_platform_db, init_platform_db
from platform_email import start_email_worker, stop_email_worker

# ── Career-specific map questions ────────────────────────────────────────────
MAP_QUESTIONS = {
    "Agriculture & Food": [
        {"zone":"Checkpoint 1 — Skills","qs":[
            {"t":"How much of your daily work involves tasks that follow the same steps each time?","opts":["Planting and watering schedules — always the same","Seasonal planning with some variation","Every season brings new challenges","Constantly adapting to unpredictable conditions"],"sc":[5,12,18,25]},
            {"t":"How often do you make judgment calls that require reading the land, weather, or animals?","opts":["Never — I follow set instructions","Sometimes when conditions change","Often — it is central to good farming","Every day is different"],"sc":[5,10,18,25]},
            {"t":"Which best describes the core skill your role depends on?","opts":["Data recording and reports","Operating machinery and equipment","Observing and responding to living things","Training others and community work"],"sc":[5,12,18,22]},
        ]},
        {"zone":"Checkpoint 2 — Work style","qs":[
            {"t":"How much of your work happens outdoors in unpredictable conditions?","opts":["Office or lab only","Mostly controlled environment","Split between field and office","Fully outdoors, season to season"],"sc":[5,10,18,25]},
            {"t":"How often do you collaborate with farmers, communities, or extension workers?","opts":["I work independently","Occasionally with a team","Frequently — coordination is key","Community engagement is my entire role"],"sc":[5,10,18,25]},
            {"t":"How much does your role depend on local knowledge — soil, climate, community?","opts":["Not at all — data tells me everything","A little local context","Quite a lot","Local knowledge is irreplaceable in my role"],"sc":[5,10,18,25]},
        ]},
        {"zone":"Checkpoint 3 — Future","qs":[
            {"t":"How comfortable are you adopting new farming technologies?","opts":["I avoid them if I can","I manage when required","I pick them up fairly easily","I actively seek agri-tech solutions"],"sc":[5,10,18,25]},
            {"t":"How much has climate change shifted your work in the last 3 years?","opts":["No change at all","Minor adjustments","Significant adaptation","Complete transformation of approach"],"sc":[5,10,18,25]},
            {"t":"How aware are you of how AI and drones are affecting agriculture?","opts":["Not at all","Heard about it vaguely","I follow developments","I actively use or evaluate these tools"],"sc":[5,12,20,25]},
        ]},
    ],
    "Business & Finance": [
        {"zone":"Checkpoint 1 — Skills","qs":[
            {"t":"How much of your daily work involves processing data or filling in the same forms?","opts":["Almost everything","About half my day","A small part","Rarely — my work is constantly different"],"sc":[5,12,18,25]},
            {"t":"How often do you make judgment calls that require reading people or context?","opts":["Never — I follow set rules","Occasionally","Often","It is the core of my job"],"sc":[5,10,18,25]},
            {"t":"Which best describes the core skill your role relies on?","opts":["Data entry and number processing","Financial analysis and modelling","Client relationships and negotiation","Strategic advisory and leadership"],"sc":[5,12,18,22]},
        ]},
        {"zone":"Checkpoint 2 — Work style","qs":[
            {"t":"How much of your work involves interacting face-to-face with clients or stakeholders?","opts":["Fixed desk — screen only","Mostly internal communication","Regular client or stakeholder contact","Relationships are my primary output"],"sc":[5,10,18,25]},
            {"t":"How often do you navigate complex regulations or compliance requirements?","opts":["I follow simple rules","Basic compliance tasks","Regular interpretation required","Deep regulatory expertise is essential"],"sc":[5,10,18,25]},
            {"t":"How much does your role depend on trust and long-term relationship building?","opts":["Not at all","A little","Quite a lot","Trust is the foundation of everything I do"],"sc":[5,10,18,25]},
        ]},
        {"zone":"Checkpoint 3 — Future","qs":[
            {"t":"How comfortable are you using new financial software or AI tools?","opts":["I avoid them","I manage when required","I pick them up fairly easily","I actively seek better tools"],"sc":[5,10,18,25]},
            {"t":"Has your role changed significantly due to automation in the last 3 years?","opts":["No change","Minor changes","Moderate changes","Significant transformation"],"sc":[5,10,18,25]},
            {"t":"How aware are you of how AI is reshaping finance and business in Kenya?","opts":["Not at all","Heard about it","I follow developments","I actively track fintech and AI trends"],"sc":[5,12,20,25]},
        ]},
    ],
    "Healthcare": [
        {"zone":"Checkpoint 1 — Skills","qs":[
            {"t":"How much of your daily work involves following set clinical protocols?","opts":["Almost entirely — strict protocols","About half clinical, half judgment","Mostly judgment-based","Every patient presents a unique challenge"],"sc":[5,12,18,25]},
            {"t":"How central is empathy and emotional presence to your role?","opts":["Not really — technical skill matters more","Sometimes important","Often essential","It is the heart of what I do"],"sc":[5,10,18,25]},
            {"t":"Which best describes your core clinical skill?","opts":["Data entry and documentation","Technical procedures and diagnostics","Patient communication and counselling","Complex clinical reasoning and decision-making"],"sc":[5,12,18,22]},
        ]},
        {"zone":"Checkpoint 2 — Work style","qs":[
            {"t":"How unpredictable is your clinical environment day to day?","opts":["Very predictable — scheduled procedures","Mostly scheduled with some emergencies","Frequent unplanned situations","Emergency and crisis response is constant"],"sc":[5,10,18,25]},
            {"t":"How often do you coordinate with other healthcare providers?","opts":["I work independently","Occasional handovers","Regular multidisciplinary team work","I lead care coordination across teams"],"sc":[5,10,18,25]},
            {"t":"How much does patient trust drive outcomes in your role?","opts":["Not a major factor","Somewhat helpful","Very important","Impossible to deliver care without it"],"sc":[5,10,18,25]},
        ]},
        {"zone":"Checkpoint 3 — Future","qs":[
            {"t":"How comfortable are you with AI diagnostic tools and health tech?","opts":["I avoid them","I manage when required","I adopt them readily","I actively seek clinical AI solutions"],"sc":[5,10,18,25]},
            {"t":"Has AI or automation changed your clinical workflow in the last 3 years?","opts":["No change","Minor changes","Moderate changes","Significant transformation"],"sc":[5,10,18,25]},
            {"t":"How aware are you of AI's impact on your specific clinical specialty?","opts":["Not at all","Heard about it vaguely","I follow health AI developments","I actively track clinical AI in my field"],"sc":[5,12,20,25]},
        ]},
    ],
    "Information Technology": [
        {"zone":"Checkpoint 1 — Skills","qs":[
            {"t":"How much of your work involves writing or debugging code that follows predictable patterns?","opts":["Almost everything","About half","A smaller portion","I design systems, others write the code"],"sc":[5,12,18,25]},
            {"t":"How often do you make architecture or product decisions that require deep context?","opts":["Never — I implement specs","Occasionally","Often","System and product thinking is my core value"],"sc":[5,10,18,25]},
            {"t":"Which best describes your highest-value technical skill?","opts":["Scripting and automation","Software development and testing","System design and architecture","Technical leadership and strategy"],"sc":[5,12,18,22]},
        ]},
        {"zone":"Checkpoint 2 — Work style","qs":[
            {"t":"How much of your work involves cross-functional collaboration with non-technical teams?","opts":["I work in an engineering silo","Occasional cross-team work","Regular cross-functional coordination","I bridge technical and business teams constantly"],"sc":[5,10,18,25]},
            {"t":"How often do you make judgment calls with incomplete information?","opts":["Rarely — specs are clear","Sometimes","Often","Ambiguity is my default environment"],"sc":[5,10,18,25]},
            {"t":"How much does your role depend on understanding the user or customer?","opts":["Not at all","A little","Quite a lot","User empathy drives every decision I make"],"sc":[5,10,18,25]},
        ]},
        {"zone":"Checkpoint 3 — Future","qs":[
            {"t":"How actively are you adopting AI tools into your development workflow?","opts":["I avoid them","I use them occasionally","I use Copilot, Claude Code etc regularly","AI is central to how I build things"],"sc":[5,10,18,25]},
            {"t":"How much has AI-assisted coding changed what you do in the last year?","opts":["No change","Minor changes","Meaningful shift in how I work","My role has fundamentally transformed"],"sc":[5,10,18,25]},
            {"t":"How deep is your understanding of AI and LLMs in your domain?","opts":["Not at all","Surface awareness","I follow developments closely","I actively build with AI APIs and models"],"sc":[5,12,20,25]},
        ]},
    ],
    "Education": [
        {"zone":"Checkpoint 1 — Skills","qs":[
            {"t":"How much of your teaching follows a fixed, repeatable curriculum?","opts":["Almost everything is scripted","Standard curriculum with some variation","I adapt regularly to my students","Every lesson is freshly designed"],"sc":[5,12,18,25]},
            {"t":"How central is reading your students' emotional state to your effectiveness?","opts":["Not really — content delivery matters more","Sometimes I adjust","Often essential","It drives every moment of my teaching"],"sc":[5,10,18,25]},
            {"t":"Which best describes your highest-value teaching skill?","opts":["Content delivery and marking","Lesson planning and assessment","Student mentorship and counselling","Curriculum design and school leadership"],"sc":[5,12,18,22]},
        ]},
        {"zone":"Checkpoint 2 — Work style","qs":[
            {"t":"How unpredictable are your students' needs day to day?","opts":["Very predictable — same routine","Mostly predictable","Frequent adjustments needed","Every day presents different challenges"],"sc":[5,10,18,25]},
            {"t":"How much do you work with parents, community, and other teachers?","opts":["Mostly alone in my classroom","Occasional collaboration","Regular coordination","Community partnership is central to my role"],"sc":[5,10,18,25]},
            {"t":"How much does trust and relationship with students drive learning outcomes?","opts":["Minimal — content is what matters","Somewhat helpful","Very important","Relationships determine everything in my classroom"],"sc":[5,10,18,25]},
        ]},
        {"zone":"Checkpoint 3 — Future","qs":[
            {"t":"How comfortable are you using EdTech and AI tools in your teaching?","opts":["I avoid them","I manage when required","I use them regularly","I actively seek new teaching technology"],"sc":[5,10,18,25]},
            {"t":"Have AI tutoring tools changed how students learn in your subject?","opts":["No impact at all","Minor changes","Noticeable shifts","Students are already using AI heavily"],"sc":[5,10,18,25]},
            {"t":"How aware are you of AI's potential in education?","opts":["Not at all","Heard about it vaguely","I follow EdTech developments","I actively integrate AI into my teaching"],"sc":[5,12,20,25]},
        ]},
    ],
    "default": [
        {"zone":"Checkpoint 1 — Skills","qs":[
            {"t":"How much of your daily work involves tasks that follow the same steps each time?","opts":["Almost all of it","About half","A small part","Every day is different"],"sc":[5,12,18,25]},
            {"t":"How often do you make judgment calls that require reading people or context?","opts":["Never — I follow set rules","Occasionally","Often","It is the core of my job"],"sc":[5,10,18,25]},
            {"t":"Which best describes the main skill your role relies on?","opts":["Data entry or processing","Technical or software skills","Communication and relationships","Creative or strategic thinking"],"sc":[5,12,18,22]},
        ]},
        {"zone":"Checkpoint 2 — Work style","qs":[
            {"t":"How much of your work happens in unpredictable or physical environments?","opts":["Fixed desk or screen","Mostly office, some variety","Mixed — field and office","Mostly outdoors or on-site"],"sc":[5,10,18,25]},
            {"t":"How often do you collaborate with others to solve problems?","opts":["I work alone most of the time","Occasionally in teams","Frequently with colleagues","Cross-team collaboration is my main role"],"sc":[5,10,18,25]},
            {"t":"How much does your role depend on building trust with people?","opts":["Not at all","A little","Quite a lot","It is essential — relationships are my job"],"sc":[5,10,18,25]},
        ]},
        {"zone":"Checkpoint 3 — Future","qs":[
            {"t":"How comfortable are you learning new tools or technologies for your job?","opts":["I avoid it if I can","I manage when required","I pick them up fairly easily","I actively seek new tools"],"sc":[5,10,18,25]},
            {"t":"Has your role changed significantly in the last 3 years?","opts":["No — same as always","Minor changes","Moderate changes","Almost unrecognisable"],"sc":[5,10,18,25]},
            {"t":"How aware are you of how AI is affecting your industry?","opts":["Have not thought about it","Heard about it vaguely","I follow developments","I actively track AI in my field"],"sc":[5,12,20,25]},
        ]},
    ],
}

load_dotenv()

# ── Config ────────────────────────────────────────────────────────────────────
ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY", "") if anthropic else ""
DB_PATH       = os.getenv("DB_PATH", "willaijob.db")
USE_AI_SCAN   = bool(ANTHROPIC_KEY)
ENABLE_LEGACY_GAME = os.getenv("ENABLE_LEGACY_GAME", "false").lower() == "true"

# Simple in-memory cache  {cache_key: {"data": ..., "ts": timestamp}}
_cache: dict = {}
CACHE_TTL = 7 * 24 * 3600  # 7 days

def cache_get(key: str):
    entry = _cache.get(key)
    if entry and time.time() - entry["ts"] < CACHE_TTL:
        return entry["data"]
    return None

def cache_set(key: str, data):
    _cache[key] = {"data": data, "ts": time.time()}

# ── DB Setup ──────────────────────────────────────────────────────────────────
async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS scan_cache (
                career_id TEXT PRIMARY KEY,
                risk_score INTEGER,
                terminal_lines TEXT,
                threats TEXT,
                skills TEXT,
                verdict_text TEXT,
                created_at REAL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS email_leads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL,
                career_id TEXT,
                career_title TEXT,
                risk_score INTEGER,
                avatar_class TEXT,
                xp_total INTEGER,
                created_at REAL DEFAULT (unixepoch())
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_sessions (
                session_id TEXT PRIMARY KEY,
                career_id TEXT,
                avatar_class TEXT,
                player_hp INTEGER,
                algo_hp INTEGER,
                skills_attacked TEXT,
                skills_gapped TEXT,
                tools_equipped TEXT,
                created_at REAL DEFAULT (unixepoch())
            )
        """)
        await db.commit()

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await init_platform_db()
    validation = validate_content()
    if not validation["valid"]:
        raise RuntimeError(f"Content validation failed: {validation['errors'][:5]}")
    start_email_worker()
    try:
        yield
    finally:
        await stop_email_worker()
        await close_platform_db()

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(title="Will AI Take My Job? API", version="1.0.0", lifespan=lifespan)

allowed_origins = [origin.strip() for origin in os.getenv("ALLOWED_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000").split(",") if origin.strip()]
app.add_middleware(CORSMiddleware, allow_origins=allowed_origins, allow_credentials=False,
                   allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
                   allow_headers=["Content-Type", "X-Session-Token", "X-Request-ID"])
app.add_middleware(GZipMiddleware, minimum_size=800)
app.add_middleware(SecurityAndOperationsMiddleware)

if ENABLE_LEGACY_GAME:
    app.include_router(game_router)
app.include_router(platform_router)

# ── Pydantic models ───────────────────────────────────────────────────────────
class EmailLead(BaseModel):
    email: EmailStr
    career_id: str = Field(max_length=80)
    career_title: str = Field(max_length=160)
    risk_score: int = Field(ge=0, le=100)
    avatar_class: Optional[str] = None
    xp_total: Optional[int] = 0

class SessionSave(BaseModel):
    session_id: str
    career_id: str
    avatar_class: Optional[str] = None
    player_hp: Optional[int] = 100
    algo_hp: Optional[int] = 100
    skills_attacked: list = Field(default_factory=list)
    skills_gapped: list = Field(default_factory=list)
    tools_equipped: list = Field(default_factory=list)

# ── Helper: lookup career ─────────────────────────────────────────────────────
def find_career(career_id: str) -> Optional[dict]:
    return next((c for c in CAREERS if c["id"] == career_id), None)

# ─────────────────────────────────────────────────────────────────────────────
# ENDPOINTS
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/health")
async def health():
    return {"status": "ok", "ai_scan": USE_AI_SCAN, "legacy_game": ENABLE_LEGACY_GAME, "careers": len(CAREERS)}


# ── GET /api/sectors ──────────────────────────────────────────────────────────
@app.get("/api/sectors")
async def get_sectors():
    sectors = sorted(set(c["sector"] for c in CAREERS))
    counts = {s: sum(1 for c in CAREERS if c["sector"] == s) for s in sectors}
    return {"sectors": [{"name": s, "count": counts[s]} for s in sectors]}


# ── GET /api/careers ──────────────────────────────────────────────────────────
@app.get("/api/careers")
async def search_careers(
    q: Optional[str] = Query(None, min_length=0),
    sector: Optional[str] = Query(None),
    limit: int = Query(40, le=100),
    skip: int = Query(0),
):
    results = CAREERS

    if sector and sector != "All":
        results = [c for c in results if c["sector"] == sector]

    if q and len(q.strip()) >= 2:
        q_lower = q.strip().lower()
        def match(c):
            if q_lower in c["title"].lower():
                return True
            if q_lower in c["sector"].lower():
                return True
            if q_lower in c.get("sub", "").lower():
                return True
            for alt in c.get("alt", []):
                if q_lower in alt.lower():
                    return True
            return False
        results = [c for c in results if match(c)]

    total = len(results)
    page  = results[skip: skip + limit]

    def fmt(c):
        col = "danger" if c["risk"] >= 66 else "warning" if c["risk"] >= 36 else "safe"
        return {
            "id": c["id"],
            "title": c["title"],
            "sector": c["sector"],
            "sub": c.get("sub", ""),
            "risk": c["risk"],
            "workforce": c.get("workforce"),
            "is_technical": c.get("is_technical", False),
            "roadmap_slug": c.get("roadmap_slug"),
            "risk_color": col,
        }

    return {"total": total, "careers": [fmt(c) for c in page]}


# ── GET /api/careers/{career_id} ──────────────────────────────────────────────
@app.get("/api/careers/{career_id}")
async def get_career(career_id: str = Path(...)):
    c = find_career(career_id)
    if not c:
        raise HTTPException(status_code=404, detail="Career not found")
    return c


# ── GET /api/careers/{career_id}/threats ─────────────────────────────────────
@app.get("/api/careers/{career_id}/threats")
async def get_threats(career_id: str = Path(...)):
    c = find_career(career_id)
    if not c:
        raise HTTPException(status_code=404, detail="Career not found")
    threats = SECTOR_THREATS.get(c["sector"], SECTOR_THREATS.get("Business & Finance", []))
    return {"career_id": career_id, "threats": threats[:3]}


# ── GET /api/careers/{career_id}/skills ──────────────────────────────────────
@app.get("/api/careers/{career_id}/skills")
async def get_skills(career_id: str = Path(...)):
    c = find_career(career_id)
    if not c:
        raise HTTPException(status_code=404, detail="Career not found")
    skills = c.get("skills", [])
    return {"career_id": career_id, "skills": skills}


# ── GET /api/scan/{career_id} — SSE streaming terminal ───────────────────────
@app.get("/api/scan/{career_id}")
async def scan_career(career_id: str = Path(...)):
    c = find_career(career_id)
    if not c:
        raise HTTPException(status_code=404, detail="Career not found")

    async def generate() -> AsyncGenerator[str, None]:
        # Check DB cache first
        cached = await load_scan_cache(career_id)
        if cached:
            for line in cached["terminal_lines"]:
                yield f"data: {json.dumps({'type':'line','text':line,'cached':True})}\n\n"
                await asyncio.sleep(0.08)
            yield f"data: {json.dumps({'type':'done','risk':cached['risk_score'],'verdict':cached['verdict_text']})}\n\n"
            return

        # Static lines first (always shown)
        static_lines = [
            {"text": f"> Initialising task-level career assessment...", "cls": "dim"},
            {"text": f"> Loading versioned editorial career profile.", "cls": ""},
            {"text": f"> Querying occupation: \"{c['title']}\" [{c['sector']}]", "cls": ""},
            {"text": f"> Separating task exposure from whole-job outcomes.", "cls": "dim"},
            {"text": f"> Checking human, physical, and accountability signals...", "cls": ""},
            {"text": f"> Checking AI augmentation opportunities...", "cls": "dim"},
            {"text": f"> No unsupported labour-market claims loaded.", "cls": "dim"},
            {"text": f"> Analysing task decomposition matrix for {c['title']}...", "cls": ""},
        ]

        for line in static_lines:
            yield f"data: {json.dumps({'type':'line',**line})}\n\n"
            await asyncio.sleep(0.28)

        # AI-generated lines or static fallback
        if USE_AI_SCAN:
            async for event in stream_claude_scan(c):
                yield event
        else:
            # Static fallback when no API key
            r = c["risk"]
            fallback = [
                {"text": f">   Routine cognitive tasks:       {round(r * 0.55)}% automatable", "cls": "dim"},
                {"text": f">   Routine manual tasks:          {round(r * 0.28)}% automatable", "cls": "dim"},
                {"text": f">   Complex social tasks:          {round(100 - r * 0.85)}% human-critical", "cls": "dim"},
            {"text": "> Combining task signals into an explainable status...", "cls": ""},
                {"text": "> ", "cls": ""},
                {"text": "> ANALYSIS COMPLETE.", "cls": "bright"},
                {"text": f"> Automation risk index: {r}%", "cls": "bright"},
                {"text": "> Proceeding to verdict...", "cls": "red"},
            ]
            for line in fallback:
                yield f"data: {json.dumps({'type':'line',**line})}\n\n"
                await asyncio.sleep(0.30)

            verdict = build_static_verdict(c)
            await save_scan_cache(career_id, c["risk"], [l["text"] for l in static_lines + fallback], verdict)
            yield f"data: {json.dumps({'type':'done','risk':c['risk'],'verdict':verdict})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


async def stream_claude_scan(c: dict) -> AsyncGenerator[str, None]:
    """Stream Claude-generated terminal lines then save to cache."""
    client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_KEY)

    prompt = f"""You are an AI automation analyst for the Kenyan labour market.

Career: {c['title']}
Sector: {c['sector']}
Sub-sector: {c.get('sub', '')}
Risk score (pre-calculated): {c['risk']}%

Generate exactly 8 terminal output lines that a hacker-style scanning system would show.
They should describe task categories and uncertainty. Do not invent, cite, or imply statistics, studies, worker counts, or live data.
Each line starts with ">" and uses a monospace terminal feel.
The last 2 lines should be:
"> ANALYSIS COMPLETE."
"> Automation risk index: {c['risk']}%"

Format as JSON array of objects: [{{"text": "line here", "cls": "dim|bright|red|"}}]
Return ONLY the JSON array, nothing else."""

    collected_text = ""
    try:
        async with client.messages.stream(
            model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514"),
            max_tokens=600,
            messages=[{"role": "user", "content": prompt}]
        ) as stream:
            async for text in stream.text_stream:
                collected_text += text

        # Parse Claude's response
        clean = collected_text.strip().lstrip("```json").rstrip("```").strip()
        ai_lines = json.loads(clean)

        for line in ai_lines:
            yield f"data: {json.dumps({'type':'line',**line})}\n\n"
            await asyncio.sleep(0.30)

        verdict = build_static_verdict(c)
        await save_scan_cache(c["id"], c["risk"], [l["text"] for l in ai_lines], verdict)
        yield f"data: {json.dumps({'type':'done','risk':c['risk'],'verdict':verdict})}\n\n"

    except Exception:
        # Fallback if Claude fails
        r = c["risk"]
        fallback_lines = [
            {"text": f">   Routine cognitive tasks:       {round(r * 0.55)}% automatable", "cls": "dim"},
            {"text": f">   Routine manual tasks:          {round(r * 0.28)}% automatable", "cls": "dim"},
            {"text": f">   Complex interpersonal tasks:   {round(100 - r * 0.85)}% human-critical", "cls": "dim"},
            {"text": "> Task-signal calculation complete", "cls": ""},
            {"text": "> ANALYSIS COMPLETE.", "cls": "bright"},
            {"text": f"> Automation risk index: {r}%", "cls": "bright"},
        ]
        for line in fallback_lines:
            yield f"data: {json.dumps({'type':'line',**line})}\n\n"
            await asyncio.sleep(0.28)
        verdict = build_static_verdict(c)
        yield f"data: {json.dumps({'type':'done','risk':r,'verdict':verdict})}\n\n"


def build_static_verdict(c: dict) -> str:
    r = c["risk"]
    if r >= 86:
        return f"The Algorithm has overwhelming power over {c['title']} — {r}% of core tasks are automatable. The comeback arc starts now."
    elif r >= 66:
        return f"Significant threat detected. {r}% automation risk means {c['title']} is actively being reshaped by AI across Kenya and globally."
    elif r >= 36:
        return f"Moderate threat at {r}%. AI will augment this role — {c['title']} professionals who adapt will accelerate ahead of those who don't."
    else:
        return f"Strong position — only {r}% risk for {c['title']}. Human skills dominate here. Keep your edge sharp as the landscape shifts."


async def load_scan_cache(career_id: str) -> Optional[dict]:
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT risk_score, terminal_lines, verdict_text FROM scan_cache WHERE career_id=? AND created_at > ?",
                (career_id, time.time() - CACHE_TTL)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return {
                        "risk_score": row[0],
                        "terminal_lines": json.loads(row[1]),
                        "verdict_text": row[2],
                    }
    except Exception:
        pass
    return None


async def save_scan_cache(career_id: str, risk: int, lines: list, verdict: str):
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                """INSERT OR REPLACE INTO scan_cache
                   (career_id, risk_score, terminal_lines, verdict_text, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (career_id, risk, json.dumps(lines), verdict, time.time())
            )
            await db.commit()
    except Exception:
        pass


# ── POST /api/email ───────────────────────────────────────────────────────────
@app.post("/api/email")
async def collect_email(lead: EmailLead):
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                """INSERT INTO email_leads
                   (email, career_id, career_title, risk_score, avatar_class, xp_total)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (lead.email, lead.career_id, lead.career_title,
                 lead.risk_score, lead.avatar_class, lead.xp_total)
            )
            await db.commit()
        return {"status": "ok", "message": "Email collected"}
    except Exception:
        raise HTTPException(status_code=500, detail="Email could not be saved")


# ── POST /api/session ─────────────────────────────────────────────────────────
@app.post("/api/session")
async def save_session(session: SessionSave):
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                """INSERT OR REPLACE INTO user_sessions
                   (session_id, career_id, avatar_class, player_hp, algo_hp,
                    skills_attacked, skills_gapped, tools_equipped)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (session.session_id, session.career_id, session.avatar_class,
                 session.player_hp, session.algo_hp,
                 json.dumps(session.skills_attacked),
                 json.dumps(session.skills_gapped),
                 json.dumps(session.tools_equipped))
            )
            await db.commit()
        return {"status": "ok"}
    except Exception:
        raise HTTPException(status_code=500, detail="Session could not be saved")


# ── GET /api/stats ─────────────────────────────────────────────────────────────
@app.get("/api/stats")
async def get_stats():
    """Public stats shown on homepage."""
    sectors = sorted(set(c["sector"] for c in CAREERS))
    total_workforce = sum(c.get("workforce", 0) for c in CAREERS)
    avg_risk = round(sum(c["risk"] for c in CAREERS) / len(CAREERS))
    return {
        "total_careers": len(CAREERS),
        "sectors": len(sectors),
        "total_workforce": total_workforce,
        "avg_risk": avg_risk,
        "data_points": 500,
    }


# ── GET /api/careers/{career_id}/map-questions ───────────────────────────────
@app.get("/api/careers/{career_id}/map-questions")
async def get_map_questions(career_id: str = Path(...)):
    """Returns 3 checkpoints × 3 questions tailored to the career's sector."""
    c = find_career(career_id)
    if not c:
        raise HTTPException(status_code=404, detail="Career not found")
    sector = c.get("sector", "default")
    questions = MAP_QUESTIONS.get(sector, MAP_QUESTIONS["default"])
    return {
        "career_id": career_id,
        "career_title": c["title"],
        "sector": sector,
        "checkpoints": questions,
    }


# ── Serve frontend static files (optional, for production) ───────────────────
frontend_dir = os.path.join(os.path.dirname(__file__), "frontend")
if os.path.isdir(frontend_dir):
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="static")
