# Will AI Take My Job?

A personalised, task-level AI career assessment. You pick your job, answer 12–16 adaptive
questions, and get seven explainable scores, the tasks most and least likely to change,
and a ranked set of skills to build — wrapped in a career-survival game.

Career scores are derived from published research (Microsoft Research's Copilot usage
study and the Felten/Raj/Seamans AI Occupational Exposure index), not from guesses.
See [docs/DATA_SOURCES.md](docs/DATA_SOURCES.md).

## Run it locally

```bash
python -m venv venv
venv\Scripts\activate          # Windows;  source venv/bin/activate on macOS/Linux
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Open <http://127.0.0.1:8000>. The backend serves the frontend, so there is nothing else
to start. No API keys are required — with none configured the app uses deterministic
static output and SQLite.

## Run it with Docker

```bash
cp .env.example .env      # set POSTGRES_PASSWORD at minimum
docker compose up -d --build
curl -s localhost:8000/api/v2/ready | jq
```

That brings up the app plus PostgreSQL. Full deployment, scaling, cutover and Raspberry Pi
instructions are in [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

## Layout

```
main.py                  FastAPI app, legacy endpoints, static hosting
platform_api.py          /api/v2 routes, validation, security middleware
platform_content.py      career/question/skill loading, search, validation
assessment_engine.py     deterministic scoring (seven dimensions)
platform_db.py           backend facade -> db_sqlite.py | db_postgres.py
platform_email.py        results email composition + Resend outbox
platform_llm.py          optional local model (Ollama/Gemma) for phrasing only
content/                 versioned seed data + SOC crosswalk
data/sources/            research inputs (CC BY 4.0, committed)
migrations/{sqlite,postgres}/  ordered schema migrations
frontend/                index.html, app.js, styles.css, media
scripts/                 content build, lead export, email flush, db migration
tests/                   API, content, frontend contract, browser critical path
load_tests/              k6 scenario (100 -> 2000 VUs)
```

## Configuration

Everything is environment-driven; see [.env.example](.env.example). The important ones:

| Variable | Effect |
|---|---|
| `DATABASE_URL` | `postgresql://…` for Postgres. Unset → SQLite at `DB_PATH`. |
| `ALLOWED_ORIGINS` | CORS allow-list. Set to your domain in production. |
| `WEB_CONCURRENCY` / `PG_POOL_MAX` | Worker count and pool size — see the connection budget in the deployment doc. |
| `RESEND_API_KEY` | Enables results emails. Without it, mail is queued but never sent. |
| `OLLAMA_URL` / `OLLAMA_MODEL` | Optional local model for the personalised sentence. Never used for scoring. |

## Tests

```bash
pytest tests -q                  # API, content, scoring, frontend contract
node tests/browser-smoke.mjs     # headless Chrome walk of the full journey
k6 run load_tests/scenario.js    # load profile (needs the app running)
```

## Content and data

```bash
python scripts/fetch_sources.py            # download research inputs
python scripts/build_career_evidence.py    # rescore careers from the sources
python scripts/validate_content.py         # schema, duplicates, coverage
python scripts/add_banking_careers.py      # example of extending the seed
```

## Operations

```bash
python scripts/export_leads.py --days 30   # consented leads -> leads.xlsx
python scripts/flush_emails.py --status    # outbox state
python scripts/migrate_sqlite_to_postgres.py --sqlite old.db
```

## A note on what this measures

The scores are percentile positions relative to the other careers in the dataset — how
much of your work generative AI is being used for today, and how much it could help you.
They are not probabilities that your job will disappear, and the app does not present them
as such.
