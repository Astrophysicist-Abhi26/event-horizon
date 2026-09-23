# Event Horizon 🔭

A personal radar for research events — conferences, schools, workshops, seminars and
webinars in **cosmology**, astrophysics, AI/ML, mathematics and physics — in Bengaluru,
across India, online and abroad. Collected daily, classified by field, ranked for my research,
so I never again discover a conference at RRI the day after it starts.

**Live site:** https://astrophysicist-abhi26.github.io/event-horizon/

## How it works

```
GitHub Actions (daily 08:00 IST)
 ├─ tests                      offline regression tests; a failure stops the run,
 │                             so the site keeps yesterday's good data
 ├─ scraper/scrape.py
 │   ├─ ~20 sources            each isolated: one broken site never kills the run
 │   ├─ normalise              drop past + undated events, detect Bengaluru/India/online/abroad
 │   ├─ de-duplicate           same event from several sources -> one card, sources merged
 │   ├─ classify               1 declared subject codes (arXiv / INSPIRE / tags)
 │   │                         2 word-bounded keyword rules (title + abstract)
 │   │                         3 [B] local embedding classifier, self-calibrating (free)
 │   │                         4 [C] Claude classifier, optional (needs API key)
 │   └─ score                  relevance to my research, cosmology weighted highest
 └─ notifications (GitHub Issues -> email)
     urgent   very relevant or Bengaluru events, the day they appear
     digest   every Monday: new relevant events + deadlines in the next 3 weeks
     health   only when a source newly breaks
```

## Sources

| Source | What it covers |
|---|---|
| DESC Cosmology Meetings | curated, cosmology-only calendar (LSST DESC) |
| CADC Astronomy Meetings | worldwide astronomy meetings (via the cadc2ical mirror + CADC RSS) |
| INSPIRE conferences / seminars | HEP, GR, cosmology, astro — with subject categories |
| researchseminars.org talks / conferences | math, physics, CS/stats talks worldwide, with arXiv-style topic codes and abstracts |
| AI Deadlines | allow-listed ML venues (NeurIPS, ICML, ICLR, COLT, AISTATS, UAI …) |
| ICTS, RRI, IMSc, ASI, IUCAA pages | Indian institutes, via one generic listing extractor |
| NCRA / IIA / TIFR Indico | Indian Indico servers (JSON API) |
| Watchlist | anything added by hand (`scraper/watchlist.yaml`) |

The **Source health** panel at the bottom of the site shows, for every source, whether it
worked on the last run and how many events it contributed.

## Fields

Cosmology (dark energy · large-scale structure · CMB & early universe · dark matter) ·
Astrophysics · AI/ML (ML for science · ML theory · general) · Mathematics (number theory ·
topology · algebra · geometry · probability & statistics · mathematical physics · analysis) ·
Physics (GR · high-energy theory · quantum · condensed matter · fluids & plasma).

On the site, **fields decide what you see; relevance only ranks and trims.**

## Customising

| I want to… | Edit |
|---|---|
| add a one-off conference | `scraper/watchlist.yaml` (a URL is enough) |
| add an institute's events page | `scraper/institutes.yaml` |
| change what matters to me | weights and bonuses at the top of `scraper/taxonomy.py` |
| fix a mislabelled event | add `["its title", correct.subfield]` to `scraper/labels.yaml` — used by tests and to calibrate the embedding classifier |
| add vocabulary | `RULES` in `scraper/taxonomy.py` (then run the tests) |

## Optional: Claude classification (Option C)

Repository **Settings → Secrets and variables → Actions → New repository secret**,
name `ANTHROPIC_API_KEY`. Each event is classified once and cached in
`scraper/cache/llm_labels.json`; at most 300 new events per run. Remove the secret to switch it off.

## Run locally

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m pytest -q tests                  # ~1 s, offline
EH_NO_EMBED=1 python scraper/scrape.py      # skip the embedding model for a quick run
cd docs && python3 -m http.server           # open http://localhost:8000
```
