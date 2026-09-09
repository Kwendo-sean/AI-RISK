# Will AI Take My Job? — Audit and Implementation Plan

Audit date: 2026-09-04

## Executive summary

The repository contains a visually distinctive working prototype, not a production-ready application. Its strongest asset is the dark, cinematic career-survival-game flow: career search, three-checkpoint map, champion reveal, optional selfie, terminal scan, slot-machine verdict, algorithm attack, draggable skill-card combat, XP, AI-tool loot, and a downloadable risk card. Those mechanics and the red/amber/green visual language must be preserved.

The current implementation cannot safely or credibly serve the stated launch target. The frontend is a single 1,659-line document with inline styles and global mutable state. The FastAPI backend embeds content in Python, opens a new SQLite connection for individual operations, stores combat sessions only in process memory, has permissive credentialed CORS, returns raw exception text, and has no rate limiting or production process configuration. The assessment has only five sector-specific variants, asks nine fixed questions, produces a single pre-authored percentage, and does not use the answers to calculate the displayed career risk. Career coverage is 121 Kenyan-oriented titles across 14 broad sectors, but only 21 careers have dedicated combat content; unsupported careers can silently become Office Administrator. There are no automated tests or load-test artifacts.

No screenshot files are present in the repository and no screenshot attachment was available to the runtime. The existing rendered application and its source styles are therefore the audited visual reference.

## What currently exists

### Stack and architecture

- Backend: Python, FastAPI 0.135, Pydantic 2, aiosqlite, Uvicorn, Anthropic SDK, HTTPX.
- Frontend: one static `frontend/index.html` containing all markup, CSS, and JavaScript; GSAP 3.12 and Three.js r128 are loaded from public CDNs; Google Fonts are loaded remotely.
- Database: a committed 60 KiB SQLite file (`willaijob.db`) using the default `DELETE` journal mode.
- Authentication: none. A caller-supplied session ID is accepted for the legacy save endpoint.
- State: page state in the global `G` JavaScript object, scan cache and lead/session rows in SQLite, and combat sessions in a Python process-level dictionary.
- Content: `careers_data.py` contains 121 career dictionaries and sector threats; `main.py` embeds question content; `gamebackendv2.py` embeds combat skills and tool recommendations.
- Deployment: no requirements lock/manifest in the repository, no Dockerfile, no process file, no reverse-proxy configuration, no health/readiness distinction, and no rollback instructions.
- Tests: none discovered.

### Existing pages and user journey

The frontend is a single document with eight routed screen states:

1. Career browser with substring search and sector filters.
2. Three-checkpoint personality/career map with nine questions and Career HP.
3. Optional selfie/avatar capture.
4. streaming terminal scan over Server-Sent Events.
5. slot-machine risk verdict.
6. algorithm threat-card attack.
7. draggable skill-card combat.
8. AI-tool arsenal, XP total, gaps, roadmap link, and risk-card download/share.

Browser hash history exists, but deep-linking into later screens starts without required state. Refreshing loses all progress. Back navigation reruns initialization and can duplicate side effects.

### Existing APIs

- `GET /api/health`
- `GET /api/stats`
- `GET /api/sectors`
- `GET /api/careers`
- `GET /api/careers/{id}`
- `GET /api/careers/{id}/threats`
- `GET /api/careers/{id}/skills`
- `GET /api/careers/{id}/map-questions`
- `GET /api/scan/{id}` (SSE)
- `POST /api/email`
- `POST /api/session`
- `GET /api/game/health`
- `GET /api/game/careers`
- `POST /api/game/start`
- `POST /api/game/play-card`
- `POST /api/game/equip-weapons`
- `GET /api/game/session/{id}`

### Career and content coverage

- 121 careers, 14 sectors, with fields: ID, title, sector, sub-sector, risk, workforce, aliases, six short skill strings, technical flag, and optional roadmap slug.
- Sector distribution: Agriculture & Food 10; Business & Finance 14; Healthcare 15; IT 14; Education 8; Engineering 6; Skilled Trades 8; Media & Creative 8; Legal & Governance 6; Transport & Logistics 7; Hospitality & Tourism 6; Social & Community 6; Science & Research 7; Informal Economy 6.
- Only Agriculture, Business & Finance, Healthcare, IT, and Education have tailored question sets. The other nine sectors use one generic fallback.
- Only 21 career keys have combat-skill decks. Only 25 tool cards exist, most centered on general-purpose office AI products.
- Search is case-insensitive substring matching. It has no relevance ranking, normalization, typo tolerance, hybrid-role flow, or first-class unknown-career support.

### Current scoring and recommendations

- The prominent risk percentage is a fixed number stored on each career; assessment responses do not change it.
- Career HP is the sum of answer points divided by the maximum available points. It mixes unrelated constructs into one number without documented directionality or calibration.
- Champion selection uses overall HP plus answer positions rather than named constructs.
- Threat damage is sector-based, then transferred into a forced 100-point zero-sum HP display.
- Combat is randomized and uses a separate, smaller career mapping. The observed Boda Boda journey resolved to Office Administrator.
- Tool recommendations use word overlap against declared skill gaps, with a career-tag bonus. They do not produce an action plan or explain career-stage relevance.
- No confidence/data-coverage calculation exists. Results use precise percentages and claims such as named datasets, worker counts, Monte Carlo iterations, and report references without source metadata.

## What must be preserved

- The “Will AI Take My Job?” premise and recognizable dark career-survival scan identity.
- Career selection, scan sequence, threat reveal, Career HP, champion archetype, skill combat, XP, levels/ranks, unlocks, career map, action recommendations, risk-card concept, and replay.
- Fast feedback, dramatic transitions, red/coral threat language, amber progression, green secure states, terminal styling, and game-like narrative.
- Useful Kenya/Africa and informal-economy coverage already present in the seed data.
- Static fallback behavior when no external AI provider is configured.
- Existing legacy endpoint paths during the transition where feasible.

## Problems discovered

### Product and data integrity

- Onboarding does not collect a name, career stage, industry, region, education, or experience.
- Email is requested before the assessment despite not being required; the copy implies delivery that the backend does not implement.
- Risk is not calculated from the user’s answers.
- Question records lack IDs, construct IDs, tags, weights, scoring dimensions, explanations, and routing/follow-up rules.
- Most users receive generic questions; all receive exactly nine.
- No semantic duplicate validation exists for questions or skills.
- Career records lack responsibilities, human/technical skills, tools, pathways, task characteristics, opportunity paths, evidence, geography notes, and dataset versions.
- Career naming and mappings diverge between the main dataset and combat dataset.
- Unsupported career fallback is silent and materially misleading.
- Skill cards are often task labels or software advertisements rather than structured, career-development recommendations.
- Result language overstates scientific certainty and includes unsupported research/data claims.

### Reliability and scale

- In-memory combat sessions fail across restarts and multiple workers.
- A new SQLite connection is opened for each database operation; no configured busy timeout, WAL, pooling strategy, or migration system exists.
- Synchronous game endpoints mutate shared process memory and randomized state.
- Scan requests deliberately sleep for several seconds, holding many SSE connections.
- In-process cache is unbounded and is not shared across workers.
- External AI calls have no explicit timeout, retry budget, concurrency guard, cost guard, or distributed deduplication.
- Static assets are not fingerprinted, compressed, locally vendored, or given cache policies.
- The always-running WebGL network rebuilds pair distances every animation frame and does not stop for reduced motion, hidden tabs, or constrained devices.
- No load tests, runtime metrics, worker configuration, or capacity evidence exists.

### Security and privacy

- `allow_origins=["*"]` is combined with credential support.
- There is no rate limiting, request-size guard, trusted-host policy, or security-header middleware.
- Error responses can expose raw exception details.
- Session IDs are supplied by callers and no ownership token protects saved state.
- No deletion API exists.
- Email validation model imports `EmailStr` but the endpoint uses plain `str`.
- Selfies are retained as large base64 strings in page memory and can unintentionally increase persisted payload size if state saving is added naively.
- Analytics/observability are absent; current logs can include raw request details under common server configurations.
- The committed database and absent `.env.example` create operational and privacy risks.

### Accessibility and responsive UX

- Most interactive elements are `div`/SVG click targets without keyboard semantics.
- Focus states, skip navigation, live announcements, dialog semantics/focus trapping, and accessible dynamic validation are absent.
- Text frequently uses 8–11 px sizes and low-opacity white.
- Several controls do not meet the 44×44 px target.
- Skill combat depends on drag gestures, with no keyboard/button alternative.
- Full-screen fixed layouts and hidden body overflow are fragile on mobile keyboards and short viewports.
- Three-column threat layouts and absolute card positions can be cramped at 320–390 px.
- Reduced-motion CSS shortens animations but the WebGL loop and timed scan still run.
- Color is sometimes the only status signifier.

### Maintainability

- UI, styles, content, API calls, scoring, routing, canvas rendering, and persistence are interleaved in one HTML file.
- Content is duplicated across three Python/JavaScript locations.
- Mutable defaults are used in the legacy Pydantic session model.
- The README describes directories and ports that do not match the repository.
- Mojibake is visible when files are read through the current Windows code page, indicating an encoding/tooling risk that must be guarded with UTF-8.

## Proposed architecture

Retain FastAPI and a progressively enhanced static frontend, but separate responsibilities:

```text
Browser UI
  ├─ onboarding/profile + private local session credential
  ├─ career search and unknown/hybrid role flow
  ├─ adaptive assessment renderer
  ├─ scan + battle presentation
  └─ explainable results, career map, skills, XP and actions
                 │ JSON/SSE
FastAPI application
  ├─ security/limits/observability middleware
  ├─ career taxonomy/search service
  ├─ deterministic question-selection service
  ├─ multidimensional scoring service
  ├─ recommendation/game service
  ├─ persistence repository
  └─ optional bounded AI enrichment with static fallback
                 │
Versioned structured content + durable database
```

Source content will live in versioned JSON seed files with explicit schemas. Runtime validators will fail fast on invalid IDs, duplicate constructs, missing mappings, unused questions, or invalid scoring. The frontend will be split into semantic HTML, CSS, and JavaScript modules without introducing a heavy framework or build tool for this launch.

## Database changes

Add ordered SQL migrations and these durable entities:

- `schema_migrations`: applied migration versions.
- `user_profiles`: opaque session ID, hashed access token, first name, career/stage/industry/region and optional education/experience, timestamps, expiry/version.
- `assessment_sessions`: selected career or fallback description, deterministic question sequence, status, score/result JSON, XP/rank, version, timestamps.
- `assessment_answers`: unique `(assessment_id, question_id)`, normalized answer, score contribution, timestamp.
- `game_events`: idempotent game actions and XP awards.
- `analytics_events`: allow-listed anonymous event names and non-PII properties with retention support.
- `scan_cache`: versioned cached scan output with expiry.
- legacy lead/session tables retained only for compatibility, with indexes and safer validation.

SQLite will be configured for local/single-node use with WAL, foreign keys, busy timeout, bounded writes, indexes, and transactionally idempotent answer handling. Production guidance will require a managed PostgreSQL-compatible deployment for horizontal scaling; Redis or an equivalent shared cache/rate-limit store is recommended at multiple replicas. The app will not claim that SQLite proves 2,000-user capacity.

## Content-system changes

- Add a documented career schema with all requested dimensions and evidence metadata.
- Transform the existing 121-career seed into normalized, versioned career records and add coverage for missing major families and specified emerging-market roles.
- Add aliases, normalized search terms, family/industry mappings, region notes, and explicit fallback profiles.
- Create modular questions with IDs, construct IDs, response options, dimension effects, weights, tags, stage rules, rationale, and optional follow-ups.
- Select 12–20 questions deterministically from universal, family, stage, and conditional modules; prevent duplicate constructs in one journey.
- Create structured skill/action cards with difficulty, time, impact, first action, pathway, prerequisites, XP, unlock rules, and career/family tags.
- Add exact and normalized similarity validators plus coverage reporting.
- Treat risk as a transparent task-change assessment, not a job-disappearance probability.

## Performance plan

1. Remove per-page synchronous AI generation; use versioned cached/static scan narratives by default.
2. Make scoring deterministic and CPU-cheap; persist answer writes idempotently.
3. Configure database pragmas locally and publish PostgreSQL production settings, indexes, pool sizing, timeouts, and migration strategy.
4. Add process-safe rate limiting with an explicit single-process fallback and document the shared-store production requirement.
5. Add response compression, cache headers, ETags for content, bounded payloads, and same-origin API defaults.
6. Replace unconditional CDN/runtime dependencies where practical and suspend visual animation when hidden or reduced-motion is requested.
7. Add readiness/liveness endpoints, request IDs, structured logs, latency/server-timing metrics, safe error handling, and integration hooks.
8. Add a repeatable k6 workload for 100/500/1,000/2,000 virtual users and record only actually measured results.

## Implementation phases

### Phase 1 — Foundation and content

- Add dependency/environment manifests, migration runner, database repository, schemas, validation, and versioned seed content.
- Add career normalization/fuzzy search and fallback/hybrid-role support.
- Add unit tests for content validity, duplicate detection, coverage, search, routing, and scoring.

### Phase 2 — Personalized assessment

- Add privacy-conscious onboarding and profile edit/delete/reset.
- Add secure resume credentials and durable assessment progress.
- Implement adaptive 12–20-question routing and explainable multidimensional scoring.

### Phase 3 — Full experience redesign

- Refactor frontend assets and rebuild every screen with semantic, responsive components.
- Preserve scan, map, champion, battle, XP, ranks, unlocks, results, and replay.
- Add mobile/keyboard alternatives and accessible announcements.

### Phase 4 — Production hardening

- Add validation, security headers, origin policy, rate limits, safe errors, caching, compression, logging, health/readiness, and analytics events.
- Add Docker/process configuration, migration-safe release/rollback steps, and monitoring integration points.

### Phase 5 — Verification

- Run unit/integration/API/persistence/content/scoring tests.
- Run responsive browser and accessibility checks where local browser tooling permits.
- Run progressive local load tests and document hardware/context, metrics, bottlenecks, and the exact production procedure.
- Produce all required architecture, schema, accessibility, security, scaling, deployment, coverage, and launch documents.

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| Career data implies unsupported scientific certainty | Use transparent dimensions, evidence/coverage metadata, ranges/status language, and an explicit disclaimer. |
| 121 legacy profiles are shallow | Preserve them, enrich by family templates, hand-author priority careers, report fallback depth, and make gaps visible in coverage output. |
| SQLite write contention | WAL/busy timeout for local testing; managed PostgreSQL and shared cache/rate limiting for multi-instance production. |
| External AI latency/cost/failure | Static deterministic output by default, strict timeout/retry/concurrency limits, cache, deduplication, and non-blocking fallback. |
| Breaking the recognizable game | Preserve the named phases and mechanics; refactor presentation and logic incrementally with critical-path tests. |
| Mobile drag interaction excludes users | Keep drag where supported and add equivalent labeled buttons/keyboard controls. |
| CDN outage or third-party drift | Eliminate nonessential dependencies, pin unavoidable assets, provide system-font and no-animation fallbacks. |
| False confidence from local load tests | Clearly label measured local results, publish environment limits, and require staging tests at production topology before launch. |
| Schema/content updates corrupt active sessions | Version content, snapshot question IDs per assessment, use additive migrations, and retain compatible readers through rollback window. |

## Audit acceptance gate

This document completes the required pre-implementation audit gate. Major behavior and architecture work may proceed only with the preservation constraints above and with testable, reversible phases.
