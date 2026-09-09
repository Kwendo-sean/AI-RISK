# Deployment plan

Target: a public GitHub repo that anyone can clone and run with one command, deployed
with Docker on your server, backed by PostgreSQL, sized for 200+ concurrent users, with
results emails through Resend and an offline Raspberry Pi variant.

---

## 1. What changes from the current deployment

| | Before | After |
|---|---|---|
| Runtime | `uvicorn main:app` on the host | Docker image, `docker compose up -d` |
| Database | SQLite file next to the code | PostgreSQL 16 in a container, volume-backed |
| Workers | 1 process | `WEB_CONCURRENCY` workers (default 4) |
| Schema changes | manual | ordered migrations applied at boot, under an advisory lock |
| Secrets | ad hoc | `.env`, never committed |
| Scan capture | none | every emailed scan stored in `scan_leads` |
| Email | none | Resend, via a durable outbox |
| Rollback | redeploy and hope | tagged image + database dump, documented below |

The application code is unchanged between backends. `DATABASE_URL` decides which store
is used, so the Pi can run SQLite while the server runs Postgres from the same image.

---

## 2. Prerequisites

- A host with Docker Engine 24+ and the Compose plugin. 2 vCPU / 4 GB RAM comfortably
  serves 200 concurrent users; 1 vCPU / 2 GB works with `WEB_CONCURRENCY=2`.
- A domain pointed at the host, if you want TLS (recommended).
- A Resend account with a verified sending domain, if you want emails to actually leave.

## 3. First deployment

```bash
git clone https://github.com/<you>/<repo>.git
cd <repo>
cp .env.example .env
```

Edit `.env` — at minimum:

```ini
POSTGRES_PASSWORD=<a long random string>
DATABASE_URL=postgresql://willaijob:<same password>@db:5432/willaijob
ALLOWED_ORIGINS=https://yourdomain.example
PUBLIC_URL=https://yourdomain.example
RESEND_API_KEY=re_...
EMAIL_FROM=Future Skills <results@yourdomain.example>
WEB_CONCURRENCY=4
```

Then:

```bash
docker compose up -d --build
docker compose logs -f app        # watch migrations apply on first boot
curl -s localhost:8000/api/v2/ready | jq
```

`ready` must report `"status": "ready"`, `database.engine: "postgres"` and
`content.errors: 0`. It also reports the email outbox and local-model status.

Migrations run automatically at start-up. With several workers booting at once, one
takes a Postgres advisory lock and the rest wait, so concurrent boots cannot race.

## 4. TLS and reverse proxy

The app sets its own security headers and trusts `X-Forwarded-*` (`--proxy-headers` in
the Dockerfile). Put Caddy in front for automatic certificates:

```caddyfile
yourdomain.example {
    encode zstd gzip
    reverse_proxy localhost:8000
}
```

Then set `ALLOWED_ORIGINS` and `PUBLIC_URL` to the `https://` origin and restart the app.

## 5. Replacing the existing (non-Docker) deployment

Do this in the order below; the only irreversible step is the DNS/port switch.

1. **Bring the new stack up on a spare port.** In `.env` set `PORT=8080`, run
   `docker compose up -d --build`, and check `/api/v2/ready` on 8080.
2. **Carry over existing data**, if the old SQLite file has anything worth keeping:
   ```bash
   docker compose cp /path/to/willaijob.db app:/tmp/old.db
   docker compose exec app python scripts/migrate_sqlite_to_postgres.py --sqlite /tmp/old.db
   ```
   The script is idempotent (`ON CONFLICT DO NOTHING`) and prints per-table counts, so
   you can dry-run it, inspect, and run it again.
3. **Stop the old service** (`systemctl stop <old-unit>` or kill the uvicorn process),
   and confirm nothing is left on port 80/8000: `ss -ltnp`.
4. **Move the new stack onto the real port**: set `PORT=8000` (or point Caddy at it) and
   `docker compose up -d`.
5. **Verify** the full journey in a browser, plus `/api/v2/ready`.

**Rollback.** Keep the previous image tag and a dump from just before cutover:

```bash
docker compose exec db pg_dump -U willaijob willaijob > backup-$(date +%F).sql
# to roll back:
docker compose down
git checkout <previous-tag> && docker compose up -d --build
cat backup-<date>.sql | docker compose exec -T db psql -U willaijob willaijob
```

Migrations are additive (new tables and columns only), so the previous image can read a
newer database. That is what makes rollback safe — keep it that way.

---

## 6. Handling 200+ concurrent users

**Connection budget.** This is the constraint people usually get wrong:

```
PG_POOL_MAX (12) x WEB_CONCURRENCY (4) = 48 connections
Postgres max_connections = 120          -> comfortable headroom
```

If you raise workers, lower `PG_POOL_MAX` to keep the product under ~70% of
`max_connections`. Compose already sets Postgres tuned for a small host
(`shared_buffers=256MB`, `synchronous_commit=off`).

**Why 200 concurrent is not 200 queries per second.** A scan is 12-16 question requests
spread over two to four minutes, so 200 people in session is roughly 2-4 writes/second —
trivial for Postgres. The load that matters is burst concurrency at the same moment, which
is why the pool and worker count matter more than raw throughput.

**Indexes in place** (see `migrations/postgres/`):

| Table | Index | Serves |
|---|---|---|
| `user_profiles` | `(session_id, token_hash)` | every authenticated request |
| `user_profiles` | `(expires_at)` | retention sweeps |
| `assessment_sessions` | `(session_id, updated_at DESC)` | resume-latest lookup |
| `assessment_sessions` | `(status, created_at DESC)` | reporting |
| `assessment_answers` | PK `(assessment_id, question_id)` | idempotent answer upsert |
| `game_events` | PK `event_id`, `(assessment_id, created_at)` | duplicate suppression |
| `analytics_events` | `(created_at)`, `(event_name, created_at)` | analytics queries |
| `scan_leads` | `(created_at DESC)`, `(marketing_consent, created_at DESC)`, `(email)`, `(career_id)` | export |
| `email_outbox` | partial `(created_at) WHERE status='queued'` | outbox flush |

The email outbox claims work with `FOR UPDATE SKIP LOCKED`, so multiple workers never
send the same message twice.

**What was actually measured.** 200 concurrent full journeys (profile -> 14 answers ->
complete -> email capture, ~3,600 requests) against PostgreSQL 16 in Docker with four
uvicorn workers:

| Metric | Result |
|---|---|
| Journeys completed | 200/200, no errors |
| Throughput | 127 requests/second |
| Wall clock | 28.3s for the whole burst |
| Single-request latency (idle) | 5-30ms server time; career search 2-13ms |

Read that carefully: the load generator fires all 200 journeys with **zero think time**,
so it is a burst test, not a simulation. Real users spend 10-30s per question, so 200
people mid-scan generate roughly 7-20 requests/second — an order of magnitude below what
this handled. The p50 journey time of 26s in the burst is queuing, not per-request latency.

Caveat: measured on a Windows development laptop (app and database on the same machine).
A Linux server with the database on its own volume will do better, but the number to
quote publicly is the one you measure on your own production topology.

**Load test before you trust any of this:**

```bash
k6 run -e BASE_URL=https://yourdomain.example load_tests/scenario.js
```

The scenario ramps 100 → 500 → 1000 → 2000 virtual users with thresholds at
`p(95) < 500ms` and `<1%` failures. Run it against staging at the production topology.
Local numbers on a laptop prove nothing about the server — record the environment
alongside any figure you quote.

---

## 7. Routine operations

```bash
# Export consented leads for a campaign
docker compose exec app python scripts/export_leads.py --days 30 -o /tmp/leads.xlsx
docker compose cp app:/tmp/leads.xlsx ./leads.xlsx

# Email queue
docker compose exec app python scripts/flush_emails.py --status
docker compose exec app python scripts/flush_emails.py

# Backups (put this in cron, keep 7 daily + 4 weekly off-host)
docker compose exec -T db pg_dump -U willaijob willaijob | gzip > backup-$(date +%F).sql.gz

# Refresh career scores after editing the crosswalk or pulling new source data
docker compose exec app python scripts/fetch_sources.py
docker compose exec app python scripts/build_career_evidence.py
```

**Monitoring.** `/api/v2/ready` returns database latency, content validity, outbox counts
and local-model status — point your uptime check at it, not at `/`. Every response
carries `X-Request-ID` and `Server-Timing` for correlation.

**Privacy.** `scan_leads` holds personal data. Only rows with `marketing_consent = true`
are exported by default; `--all` exists for support, not for bulk mail. Deleting a
profile cascades to its leads. `PROFILE_TTL_DAYS` (default 90) bounds retention.

---

## 8. Raspberry Pi deployment (offline)

The app was built to run with no internet at runtime: fonts and scripts are served
locally, there are no CDN dependencies, and a test enforces that
(`test_no_external_runtime_dependencies`). The parts that need a network are optional.

**What works fully offline:** career search, the whole assessment, scoring, results,
skill recommendations, lead capture, and the Excel export.

**What degrades gracefully:** results emails are written to `email_outbox` and stay
`queued`. Nothing is lost. When the Pi next has a connection — or from any machine that
can reach both the database and Resend — run `python scripts/flush_emails.py` to drain it.

**Recommended Pi setup** (Pi 4 or 5, 64-bit Raspberry Pi OS):

```bash
git clone https://github.com/<you>/<repo>.git && cd <repo>
cp .env.example .env
# Leave DATABASE_URL unset -> SQLite at /data/willaijob.db. On one node with a
# handful of concurrent users, SQLite in WAL mode is the right call, not Postgres.
docker build -t futureskills .
docker run -d --name futureskills -p 8000:8000 \
  -v futureskills-data:/data --env-file .env --restart unless-stopped futureskills
```

The image builds for arm64 as-is. If you build on your laptop instead of on the Pi, use
`docker buildx build --platform linux/arm64`.

### Gemma on the Pi

Install Ollama and pull a small Gemma:

```bash
curl -fsSL https://ollama.com/install.sh | sh    # needs internet once, at install time
ollama pull gemma3:1b                            # ~815 MB; use gemma3:4b on a Pi 5 / 8 GB
```

Point the app at it in `.env`:

```ini
OLLAMA_URL=http://host.docker.internal:11434   # or the Pi's LAN IP
OLLAMA_MODEL=gemma3:1b
```

**Be clear about what the model does here.** Gemma does *not* compute the scores.
The seven dimensions, the exposure percentile and the skill ranking are calculated in
`assessment_engine.py` from the person's answers and the research datasets. That is
deliberate:

- the same answers must always produce the same numbers, and a sampled model cannot promise that;
- the result has to be explainable — we show which answers moved which dimension;
- a 1B model on a Pi would take seconds to produce a number it has no basis for.

What Gemma *does* is rewrite the finished result into a sentence or two aimed at this
person's job, stage and region (`platform_llm.py`). It runs after scoring, with an 8s
timeout and a length sanity check; if it is slow, missing or rambling, the deterministic
sentence is used and the user sees no difference. On a Pi 4 expect roughly 2-6s for
~120 tokens with `gemma3:1b` — acceptable because it is off the critical path, and it is
the only thing on the Pi that touches a model at all.

If you later want the Pi to do more model work, the honest options are: pre-generating
per-career narrative text offline and shipping it as content, or letting the model draft
the *email* body rather than the on-screen result. Both keep scoring deterministic.

---

## 9. Before making the repo public

- [ ] `.env` is gitignored and has never been committed (`git log -p -- .env` returns nothing).
- [ ] No API keys in the history: `git log -p | grep -iE "re_[a-z0-9]{20}|sk-ant-"`.
- [ ] `*.db` files are gitignored — the old `willaijob.db` was committed previously, so
      purge it from history (`git filter-repo --path willaijob.db --invert-paths`) or accept
      that it stays in old commits. It contains real lead rows, so purge it.
- [ ] `leads.xlsx` and any export is gitignored.
- [ ] `data/sources/` (CC BY 4.0, attributed in `docs/DATA_SOURCES.md`) is committed;
      `data/cache/` (AIOE, no redistribution licence) is not.
- [ ] `README.md` describes the actual layout and commands.
- [ ] A `LICENSE` file exists for your own code.
