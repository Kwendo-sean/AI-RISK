# Will AI Take My Job? — Full Stack Setup

## Project Structure
```
project/
├── backend/
│   ├── main.py           # FastAPI app (all API endpoints)
│   ├── careers_data.py   # 120+ Kenyan careers + threat data
│   ├── requirements.txt  # Python deps
│   └── willaijob.db      # SQLite DB (auto-created on first run)
└── frontend/
    └── index.html        # Complete frontend (screens 0–5 + Round 1)
```

## Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create .env file
cp .env.example .env
# Add your ANTHROPIC_API_KEY to .env

# Run server
uvicorn main:app --reload --port 8000
```

## Environment Variables (.env)
```
ANTHROPIC_API_KEY=sk-ant-...     # Required for AI-powered terminal scan
DB_PATH=willaijob.db             # SQLite DB path (default)
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | /api/health | Server health + feature flags |
| GET | /api/stats | Homepage stats (career count, sectors) |
| GET | /api/sectors | All sectors with career counts |
| GET | /api/careers | Search/filter careers |
| GET | /api/careers/{id} | Get single career |
| GET | /api/careers/{id}/threats | Round 1 threat cards |
| GET | /api/careers/{id}/skills | Skill combat cards |
| GET | /api/scan/{id} | SSE streaming terminal scan |
| POST | /api/email | Collect email lead |
| POST | /api/session | Save game session state |
| GET | /api/stats | Public dashboard stats |

## Frontend

Open `frontend/index.html` directly in browser, or serve it:
```bash
cd frontend
python -m http.server 3000
# Open http://localhost:3000
```

Make sure backend is running at http://localhost:8000

## Without API Key

The app works fully without an ANTHROPIC_API_KEY:
- Terminal uses static data (still looks great)
- All other screens are fully functional
- Add API key later to get Claude-generated unique terminal content per career

## Ownership

| Screen | Owner | Status |
|--------|-------|--------|
| S0: Career browser | You | DONE |
| S1: Personality trial | You | DONE |
| S2: Selfie | You | DONE |
| S3: Terminal scan | You | DONE (SSE + Claude API) |
| S4: Slot machine verdict | You | DONE |
| S5: Round 1 + Brace | You | DONE |
| S6: Skill card combat | Friend 2 | TODO |
| S7: Power-ups | Friend 2 | TODO |
| S8: Aftermath | Friend 2 | TODO |
| Kenya map (between S0–S1) | Friend 1 | TODO |

## Handoff State for Friend 2

After Round 1 completes, `G` (global state object) contains:
```js
G.career      // {id, title, sector, risk, is_technical, roadmap_slug, ...}
G.avatar      // {id, name, cls, c}
G.selfieUrl   // base64 string or null
G.playerHP    // number (reduced by Round 1 attacks)
G.algoHP      // number (= career risk score)
G.threats     // [{title, body, damage}] (3 threats from API)
G.skills      // string[] (6 skill names from API)
G.xp          // number (accumulated XP)
```

Friend 2 calls `goTo(6)` to advance to skill combat screen.
Friend 1 inserts Kenya map between `goTo(1)` and `goTo(2)` in the flow.
