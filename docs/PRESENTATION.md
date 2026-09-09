# Presenter guide — Will AI Take My Job?

Build the deck straight from this. Each section is one slide: the **title** goes on the
slide, the **bullets** are what appears (keep them short — four lines maximum), and
**Say** is what comes out of your mouth. Do not put the "Say" text on the slide.

Total: 12 slides, ~10 minutes, plus a live demo. If you only get 5 minutes, run slides
1, 3, 5, 8 and the demo.

---

## Slide 1 — Title

**On the slide**
> **Will AI Take My Job?**
> A 2-minute scan of your work, running on a Raspberry Pi

**Say**
> "Everyone in this room has had a version of the same conversation this year — will this
> thing take my job. The honest answer is that nobody can tell you that. What we *can* do
> is something more useful: show you which specific parts of your work AI is already doing,
> which parts still need you, and what to learn next. That's what this is."

---

## Slide 2 — The problem with how this question gets answered

**On the slide**
- "47% of jobs at risk" — headlines with no method
- Generic advice: "learn AI"
- Nothing that speaks to a boda rider, a bank teller, or a nurse in Nairobi

**Say**
> "The public conversation is stuck between panic and platitudes. You get a scary
> percentage with no method behind it, and advice so generic it's useless — 'learn AI'.
> And almost all of it is written about American white-collar jobs. Nobody's telling a
> credit officer in a Nairobi bank what actually changes about their Tuesday."

---

## Slide 3 — What we built

**On the slide**
- Pick your job → answer 12–16 adaptive questions
- Get 7 explainable scores, not one fake number
- See which of your *tasks* change, and what stays yours
- Ends with a ranked list of skills and a first step for each

**Say**
> "So we built a scan. You tell it your job, it asks you 12 to 16 questions — and they
> adapt, a nurse and a mechanic don't get the same questions. Then it gives you seven
> scores, each one explained, plus the specific tasks in your job most and least exposed.
> It finishes with skills to build and the first concrete action for each one. The whole
> thing takes about two minutes."

---

## Slide 4 — Where the numbers come from

**On the slide**
- Microsoft Research 2025 — 200,000 real Copilot conversations → what AI *actually* does at work
- Felten/Raj/Seamans AI Occupational Exposure index (2021)
- ILO Working Paper 140 (2025) — for developing-economy context
- 156 careers, each mapped to an occupation code, each carrying its sources

**Say**
> "This is the part I care most about. The first version had numbers we made up — and it
> showed: an electrician scored higher AI exposure than a software developer, which is
> nonsense. So we rebuilt it on published research. Microsoft released a study analysing
> two hundred thousand real conversations people had with Copilot at work — that tells you
> what AI is *actually being used for*, not what a consultant guesses. We combined that
> with the academic exposure index used across this literature, and cross-checked our
> approach against the ILO's 2025 work, which is explicitly designed to hold up outside
> rich countries. Every career in the app now carries its sources. You can check our
> working."

*If asked "where does my job's number come from" — open the results screen; the evidence
is in the API response and named in the docs.*

---

## Slide 5 — What we refuse to claim

**On the slide**
- Scores are **positions relative to other jobs**, not probabilities
- We do not predict job losses
- Physical, in-person and accountable work scores low — and the data says so

**Say**
> "We deliberately don't tell you 'you have a 70% chance of losing your job'. That number
> would be fiction. What we give you is a position: your work is more exposed than 70% of
> the other jobs in the dataset. That's a claim the data can actually support. And the
> ordering passes the smell test — copywriters, content people and journalists at the top;
> surgeons, masons, fishers at the bottom. Nobody's automating a mason from a laptop."

---

## Slide 6 — It runs on this

**On the slide**
- Raspberry Pi 5 · 4 GB RAM
- Gemma 3 1B via llama.cpp — on the device
- No internet. No cloud. No data leaving the room.

**Say**
> "Now the part that matters for this room. Everything you're about to see runs on that
> Raspberry Pi. The scoring, the database, the website, and the AI. There is no internet
> connection involved — if the venue Wi-Fi dies right now, the demo keeps working. Your
> answers never leave this device."

---

## Slide 7 — Why local matters (the real argument)

**On the slide**
- Data sovereignty: financial and career data stays in the building
- Works where connectivity doesn't
- No per-request cloud cost
- Latency you can feel

**Say**
> "This isn't a gimmick. Three real reasons. One: sovereignty — if you're handling
> people's financial or employment data, 'it never left the building' is a much easier
> conversation than 'it's encrypted in transit to Virginia'. Two: it works where the
> internet doesn't, which is most of this country on most days. Three: cost — cloud AI
> charges per request; this charges you once, for the Pi."

---

## Slide 8 — Where the AI is, and isn't

**On the slide**
- Scores: **deterministic code**, same answers → same result, always
- Gemma: **phrasing only** — turns the result into advice in your words
- If the model is slow or busy, you still get your result

**Say**
> "I want to be precise about this because it's where most AI demos oversell. The model
> does *not* compute your scores. Those come from deterministic code, so the same answers
> always give the same result and I can point at exactly which of your answers moved which
> number. A one-billion-parameter model on a Pi is not a calculator and I'm not going to
> pretend it is. What Gemma does is take the finished result and write it back to you in
> plain language about your job. And if it's busy or slow, the app falls back to the
> written copy and the visitor never notices."

*This slide wins over technical audiences. Don't skip it.*

---

## Slide 9 — Live demo

**On the slide**
> Scan → join TREPLEX-AIOT → open 10.42.0.1:8000

**Demo script** (rehearse this once; it takes 2 minutes)

1. Hold up the printed card. "Two QR codes — first joins the Wi-Fi, second opens the site."
2. Search a career the audience relates to. **Type "bank"** — 16 roles appear.
   Say: *"We added the whole banking sector last week. Teller, credit analyst, loan officer,
   SACCO officer, mobile money."*
3. Pick **Credit Analyst**. Fill the profile: mid-career, Nairobi.
4. Answer 3–4 questions out loud, then say *"I'll skip ahead"* and finish quickly.
5. On the scan screen: *"That's not a loading bar for show — it's printing the scores it
   just computed."*
6. On results, point at three things and nothing else:
   - the seven scores — *"each one named in plain English"*
   - **Why you got this result** — *"your own answers, and what each one did"*
   - the skills — *"and the first action for each, not 'learn AI'"*
7. Finish: *"All of that came off the Pi. No internet."*

**If the demo breaks:** you have the screenshots. Say *"the Pi is doing CPU inference and
we're sharing it with the room — here's what you'd see"*, show the screenshot, move on.
Do not debug on stage.

---

## Slide 10 — Under the hood (for the technical half of the room)

**On the slide**
- FastAPI + PostgreSQL in production, SQLite offline on the Pi — one image, one env var
- Verified: 200 concurrent full journeys, 127 req/s, zero errors
- Session-isolated, consent-gated, no data retained beyond 90 days

**Say**
> "Briefly for the engineers. Same container runs both ways — Postgres on the server,
> SQLite on the Pi, switched by one environment variable. We load-tested it at 200
> concurrent users end-to-end and it held with no errors. Every visitor gets their own
> session token; nobody sees anyone else's answers. And we found a real bug doing that
> testing — our rate limiter was bucketing by IP address, which means behind a carrier
> NAT, one person could throttle everybody. Fixed before anyone hit it."

---

## Slide 11 — What's next

**On the slide**
- Kenyan labour-market data layered onto the global exposure indices
- Follow-up email with your results and a 30-day plan
- More sectors, deeper informal-economy coverage

**Say**
> "Three things next. The exposure data is global — I want Kenyan labour-market data
> layered on top, because a teller in Nairobi faces different economics than one in
> Chicago. Second, the results email so people leave with a plan, not just a number.
> Third, deeper coverage of the informal economy, which is where most of this country
> actually works and where the data is thinnest."

---

## Slide 12 — Close

**On the slide**
> **Scan it. It takes two minutes.**
> TREPLEX-AIOT → 10.42.0.1:8000

**Say**
> "The booth is open for the rest of the day. Come and scan your own job — takes two
> minutes, tells you something specific, and nothing you type leaves that Pi. I'd
> genuinely like to hear whether the result matches your experience of your own work,
> because that's the only test that matters."

---

## Questions you will be asked — and answers

**"How accurate is this?"**
> "The exposure data is peer-reviewed and published; our layer on top is the mapping from
> job title to occupation code, and we mark how confident each mapping is — direct, close,
> or an analogue where no equivalent exists. The informal-economy roles are the weakest and
> we label them as indicative rather than pretending otherwise."

**"Is my data safe?"**
> "It's on the Pi. There's no cloud call in the path. You get a random session token, not
> an account. There's a button to delete everything you entered, and if you give an email
> it's only stored when you tick the box."

**"Isn't this just telling people they're doomed?"**
> "The opposite — it's a planning tool. Every result ends in skills with a first action.
> And a lot of people find their score is lower than they feared, because the parts of
> their job that need judgement, trust, or hands don't move."

**"Why Gemma and not GPT-4 / Claude?"**
> "Because it has to run with no internet. That's the constraint that drove everything.
> Gemma 3 1B fits in the Pi's memory and does the one job we need — phrasing. The
> intelligence people care about here is the scoring, and that's deterministic code with
> research behind it, not a model."

**"How many careers?"**
> "156, across 16 industries, including informal roles — boda boda, mama mboga, jua kali,
> M-Pesa agent — which you won't find in a US-built tool."

**"Can it do my industry?"**
> "If it's missing, say so and I'll add it — that's how the banking sector got in. Search
> for it now and tell me what you find."

---

## Numbers worth memorising

| | |
|---|---|
| Careers | 156 across 16 industries |
| Questions | 12–16, adaptive |
| Scores shown | 7, each explained |
| Research inputs | 3 published studies, ~200k real AI conversations behind one |
| Load tested | 200 concurrent journeys, 127 req/s, 0 errors |
| Runs on | Raspberry Pi 5, 4 GB, offline |
| Model | Gemma 3 1B via llama.cpp, phrasing only |

## Booth setup checklist

- [ ] Pi powered, `TREPLEX-AIOT` visible from a phone
- [ ] `http://10.42.0.1:8000` opens on a phone and a laptop
- [ ] Printed booth card on the table (`python scripts/make_booth_qr.py` → `booth/booth-card.html`)
- [ ] One rehearsed run-through completed today
- [ ] Screenshots on your laptop as demo backup
- [ ] Someone watching `/api/v2/ready` during the session
