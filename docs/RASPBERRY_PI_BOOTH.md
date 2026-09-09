# Raspberry Pi booth deployment (TREPLEX-AIOT)

Deploys this app onto the Pi you already have running KPIsAgent, **alongside** it. Nothing
here touches your networking, your llama-server, or your Django services.

## What already exists, and what we add

| | Existing | This app |
|---|---|---|
| Web | KPIsAgent Django on **8090** | **8000** |
| Model | llama-server on **8081** (Gemma 3 1B) | reuses the same one — no second process |
| Services | `treplex-llm`, `treplex-qcluster`, `treplex-web` | `careerscan.service` |
| Database | KPIsAgent's own | its own SQLite at `/home/treplex/careerscan/data/` |
| Network | `TREPLEX-AIOT`, 10.42.0.1 | unchanged — **do not touch** |

Visitors reach KPIsAgent at `10.42.0.1:8090` and this at `10.42.0.1:8000`. Two demos, one
Pi, one AP, one model server.

---

## 1. Install (~10 minutes, needs internet once)

Do this **before** the venue, while you still have a connection.

```bash
ssh treplex@10.42.0.1

cd ~
git clone https://github.com/<you>/<repo>.git careerscan
cd careerscan

python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt
```

`asyncpg` is in requirements and will build slowly on the Pi. It is not needed offline —
if it stalls or fails, drop it:

```bash
grep -v asyncpg requirements.txt > /tmp/req-pi.txt
.venv/bin/pip install -r /tmp/req-pi.txt
```

The app falls back to SQLite automatically when `DATABASE_URL` is unset, which is what
you want on one node anyway.

## 2. Configure

```bash
mkdir -p ~/careerscan/data
cat > ~/careerscan/.env <<'EOF'
# SQLite - one node, no server process, WAL mode. Correct choice for a booth.
DB_PATH=/home/treplex/careerscan/data/careerscan.db

# Reachable from the AP subnet and from the Pi itself.
ALLOWED_ORIGINS=http://10.42.0.1:8000,http://127.0.0.1:8000
PUBLIC_URL=http://10.42.0.1:8000

# Reuse the llama-server that is already running for KPIsAgent.
LLM_BACKEND=llamacpp
LLM_URL=http://127.0.0.1:8081
LLM_MODEL=gemma-3-1b
LLM_TIMEOUT=8
LLM_MAX_TOKENS=120
# A Pi 5 doing CPU inference thrashes above 2 in flight. Over the limit, the app
# silently uses its written copy instead of queueing.
LLM_MAX_CONCURRENCY=2

# A booth is one IP for everybody. Without this, the tenth visitor gets throttled.
RATE_LIMIT_SIGNUP_PER_MINUTE=600
RATE_LIMIT_IP_PER_MINUTE=20000

# Short retention for a public device.
PROFILE_TTL_DAYS=2

# No internet at the venue: mail is queued locally and sent later.
RESEND_API_KEY=
EOF
```

Verify it boots by hand before making it a service:

```bash
cd ~/careerscan
set -a; . ./.env; set +a
.venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000 --no-access-log
# in another shell:
curl -s http://10.42.0.1:8000/api/v2/ready
```

You want `"status":"ready"`, and under `local_model`, `"reachable": true`. If the model
shows unreachable, check the endpoint your llama-server exposes:

```bash
curl -s http://127.0.0.1:8081/health
curl -s http://127.0.0.1:8081/v1/models
```

The app talks to llama-server's OpenAI-compatible `/v1/chat/completions`. If your build
predates that, leave `LLM_URL` empty — everything else works, you just lose the
personalised sentence.

Stop it with Ctrl-C once you have seen `ready`.

## 3. systemd service

```bash
sudo tee /etc/systemd/system/careerscan.service >/dev/null <<'EOF'
[Unit]
Description=Career Scan booth app (Will AI Take My Job?)
After=network-online.target treplex-llm.service
Wants=network-online.target
# Not Requires=: the app must still start if the model server is down.

[Service]
Type=simple
User=treplex
Group=treplex
WorkingDirectory=/home/treplex/careerscan
EnvironmentFile=/home/treplex/careerscan/.env
ExecStart=/home/treplex/careerscan/.venv/bin/uvicorn main:app \
    --host 0.0.0.0 --port 8000 --no-access-log --workers 2
Restart=always
RestartSec=3
# Booth hardening: it only ever needs its own directory.
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=full
ProtectHome=read-only
ReadWritePaths=/home/treplex/careerscan/data

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now careerscan.service
systemctl status careerscan.service --no-pager
```

**Two workers, not four.** The Pi 5 has 4 cores and llama.cpp will want most of them
during inference. Two uvicorn workers leaves the model room to answer.

## 4. Verify from a phone

Join `TREPLEX-AIOT`, then open `http://10.42.0.1:8000`. Check:

- the landing page loads with its image and fonts (all local — no CDN)
- career search returns results as you type
- the whole journey completes
- `http://10.42.0.1:8000/api/v2/ready` shows `ready`

## 5. Cold boot test — do this, do not skip it

```bash
sudo shutdown -h now
```

Pull the power, wait ten seconds, plug back in. Then, **without SSH-ing in**:

1. `TREPLEX-AIOT` appears in your phone's Wi-Fi list
2. Join it
3. Open `10.42.0.1:8000` — the site is already up
4. Run one full scan
5. Open `10.42.0.1:8090` — KPIsAgent still works too
6. From a second phone, run another scan and confirm you see your own results, not the first phone's

If step 3 fails, `sudo journalctl -u careerscan -b --no-pager | tail -40`.

## 6. Print the booth card

On your laptop (not the Pi):

```bash
python scripts/make_booth_qr.py --url http://10.42.0.1:8000
# open booth/booth-card.html and print to A4
```

Two QR codes: one joins the Wi-Fi (phones read `WIFI:` payloads natively), one opens the
site. The order matters — the site QR cannot resolve until the phone is on the Pi's
network, which is why the card is numbered.

---

## Booth safety — what is already true

You asked for these; most are already in the app, so do not go building them again.

| Requirement | Status |
|---|---|
| Session isolation | Each visitor gets a random session id + bearer token. Every read is filtered by both. One visitor physically cannot fetch another's assessment — a mismatched token returns 401. |
| No cross-session leakage | No shared mutable state between requests; results are keyed to the assessment row. |
| "Clear my data" | **Delete saved progress** on the results screen. Hard-deletes the profile; assessments, answers, game events and leads cascade. |
| Retention | `PROFILE_TTL_DAYS=2` above. Expired profiles stop resolving. |
| Upload limits | No file uploads at all in this app. The optional selfie never leaves the browser. |
| Request size cap | 64 KB (`MAX_REQUEST_BYTES`), enforced in middleware. |
| Rate limiting | Per session token, with a per-IP backstop — raised above for shared-NAT booth use. |
| No sensitive logging | Request logging is 1% sampled and records path and duration, never bodies. |
| Health check | `GET /api/v2/ready` — database, content, email queue, model reachability. |
| Offline | No CDN, no external fonts, no cloud AI. A test enforces it (`test_no_external_runtime_dependencies`). |

**Operator check during the event** — run this on the Pi, or from your laptop on the AP:

```bash
watch -n 10 'curl -s http://10.42.0.1:8000/api/v2/ready; echo; free -m | head -2; uptime'
```

## Concurrency expectations

Honest numbers for this hardware:

- **Scoring and the website:** trivial. It is arithmetic over a cached in-memory dataset;
  a Pi 5 handles a booth's worth of visitors without noticing.
- **The model:** the bottleneck. Gemma 3 1B on CPU is roughly 2–6 seconds for the ~120
  tokens we ask for, and it does not parallelise well. `LLM_MAX_CONCURRENCY=2` caps it;
  visitor three gets the written copy instead of waiting. That is the right trade for a
  booth — nobody stands there watching a spinner.
- **If KPIsAgent is also mid-inference**, both demos are sharing one llama-server. Expect
  slower narration on both. Neither breaks; both fall back.

If you want to remove all model contention during a demo, set `LLM_URL=` in `.env` and
restart — the app is fully functional without it.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Site unreachable from phone | bound to localhost | confirm `--host 0.0.0.0` in the unit, `ss -ltnp \| grep 8000` |
| `ready` shows model unreachable | llama-server down or different API | `systemctl status treplex-llm`; `curl 127.0.0.1:8081/health` |
| Visitors getting 429 | rate limit too low for shared NAT | raise `RATE_LIMIT_SIGNUP_PER_MINUTE`, restart |
| Slow after many visitors | SQLite WAL growth | `sudo systemctl restart careerscan` between sessions |
| Port 8000 taken | something else bound | change the port in `.env`, the unit, and the QR card |

## Rollback

Nothing in this deployment modifies KPIsAgent, NetworkManager, or `treplex-*` services.
To remove it completely:

```bash
sudo systemctl disable --now careerscan.service
sudo rm /etc/systemd/system/careerscan.service
sudo systemctl daemon-reload
rm -rf ~/careerscan
```
