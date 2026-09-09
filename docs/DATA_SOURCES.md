# Where the career numbers come from

Every career now carries an `evidence` block naming the occupation it was scored from,
the datasets behind it and the method. Nothing on the results page is a number someone
made up, and the app no longer claims more certainty than the sources support.

## The problem this replaced

The original seed carried hand-authored figures with `"sources": []` on all 141 careers.
They were internally inconsistent — an Electrician scored higher AI exposure than a
Software Developer, and `ai_augmentation_potential` was a single constant repeated for
every career in a sector. There was no way to defend any individual number.

## Sources

### 1. Microsoft Research — *Working with AI* (2025)
Tomlinson, Jaffe, Wang, Counts & Suri. *Working with AI: Measuring the Applicability of
Generative AI to Occupations.* arXiv:2507.07935.
<https://arxiv.org/abs/2507.07935> · data: <https://github.com/microsoft/working-with-ai>

Built from 200,000 anonymised, privacy-scrubbed Bing Copilot conversations (Jan–Sep 2024),
mapped onto O\*NET work activities and aggregated to 2018 SOC occupations. It is the only
large public measure of what generative AI is *actually being used for* at work, rather
than what it might theoretically do.

Two of its columns matter here, and the distinction is the useful part:

- `ai_applicability_score_ai_nonphysical` — how much of the occupation's work activity the
  AI itself performed. Used for **exposure**.
- `ai_applicability_score_user` — how often workers asked AI for help with those
  activities. Used for **augmentation potential**.

Licence: **CC BY 4.0**. Vendored in `data/sources/` with attribution.

### 2. Felten, Raj & Seamans — AI Occupational Exposure (2021)
*Occupational, industry, and geographic exposure to artificial intelligence.*
Strategic Management Journal 42(12): 2195–2217. <https://doi.org/10.1002/smj.3286>
Data: <https://github.com/AIOE-Data/AIOE>

Links ten AI capabilities to 52 O\*NET occupational abilities, producing a standardised
exposure score (z-scores, −2.67 to +1.53) for 774 SOC occupations. It captures structural
exposure that usage data alone misses — an occupation can be highly exposed in principle
before anyone in it has opened a chatbot.

The repository declares no licence, so the file is **not** redistributed here. Run
`python scripts/fetch_sources.py` to download it into `data/cache/` (gitignored). Without
it the build still runs, using the Microsoft measure alone.

### 3. ILO Working Paper 140 (2025)
*Generative AI and Jobs: A Refined Global Index of Occupational Exposure.*
<https://www.ilo.org/publications/generative-ai-and-jobs-refined-global-index-occupational-exposure>

Task-level exposure by ISCO-08, built from 29,753 occupational tasks and 52,558 human
ratings, explicitly designed to hold up outside high-income economies. Cited for two
things: the finding that clerical support work carries the highest exposure of any major
group, and the reason our physical and informal-economy roles score low. It is not used
numerically — its published scores are ISCO-based and the paper ships no machine-readable
annex, so mapping our SOC crosswalk onto it would have added error, not accuracy.

## Method

`content/soc_crosswalk.json` maps each career to a 2018 SOC occupation with a quality flag:

- **direct** — the same job under a different name (Bank Teller → Tellers)
- **close** — same task profile, different scope (DevOps Engineer → Software Developers)
- **analogue** — no SOC equivalent exists, mostly Kenyan informal roles
  (Boda Boda Operator → Taxi Drivers). These are marked `"coverage": "indicative"` and
  should be read as directional.

`scripts/build_career_evidence.py` then computes, across all mapped careers:

```
exposure_input   = 0.6 x MS "AI performed the activity" + 0.4 x normalised AIOE
ai_exposure      = percentile rank of exposure_input
ai_augmentation_potential = percentile rank of MS "worker asked AI for help"
```

**Both are percentile positions within this dataset, not probabilities.** A career at 90
is more exposed than 90% of the other careers here. It is not "90% likely to be
automated", and the UI is worded to match. That framing is forced by the sources: AIOE is
a standardised relative index and the Microsoft score is a usage share, so neither
supports an absolute reading.

## Sanity check

Ordering after the rebuild, which is what you would expect from the literature:

| Highest exposure | | Lowest exposure | |
|---|---|---|---|
| Copywriter | 99 | Surgeon | 0 |
| Digital Content Creator | 99 | Fisher | 1 |
| Social Media Manager | 98 | Domestic Worker | 1 |
| PR Specialist | 98 | Mason | 2 |
| Journalist | 96 | Construction Worker | 3 |

Language, analysis and communication work at the top; physical, in-person and
safety-critical work at the bottom.

## Coverage and known gaps

- 156 careers, all mapped and scored; 15 banking and financial-services roles were added
  because the sector previously had one entry (Bank Teller) for the whole industry.
- SOC is a **US** classification. Task content transfers reasonably; labour-market
  conditions do not. A Kenyan bank teller faces different automation economics than a US
  one, and nothing here models that.
- The Microsoft data reflects Copilot users, which skews toward desk work with
  English-language interfaces. Informal-economy roles are the weakest part of the dataset,
  which is exactly why they are flagged `indicative`.
- Workforce estimates in the seed are unchanged and still editorial. They are not
  presented as sourced.

## Rebuilding

```bash
python scripts/fetch_sources.py           # downloads AIOE into data/cache/
python scripts/build_career_evidence.py --dry-run   # preview the ranking
python scripts/build_career_evidence.py             # write content/careers.v1.json
python scripts/validate_content.py                  # must report valid: true
```

Bump `DATASET_VERSION` in `platform_content.py` whenever the seed's
`dataset_version` changes; the app refuses to start on a mismatch.
