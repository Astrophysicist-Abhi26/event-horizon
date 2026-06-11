# Event Horizon 🔭

A personal radar for research events — conferences, workshops, schools,
seminars and lecture series in **astronomy, astrophysics, cosmology, physics,
mathematics and AI/ML** — so you never again find out about a conference at
RRI the day before it starts.

**Live site:** enable GitHub Pages (see step 4 below) and it will be at
`https://<your-username>.github.io/event-horizon/`

## How it works

```
GitHub Actions (daily, 08:00 IST)
   └── scraper/scrape.py
        ├── pulls events from every source in scraper/sources.py
        ├── scores each event 0–100 against your interest profile
        ├── writes docs/events.json  (the website's database)
        └── if NEW events score ≥ 30 → opens a GitHub Issue
                                       → GitHub emails you automatically
GitHub Pages
   └── serves docs/index.html — date range, event type, field,
       India/abroad, country, source, relevance and search filters
```

## Sources currently wired in

| Source | Coverage | Status |
|---|---|---|
| huggingface/ai-deadlines | All major AI/ML conferences + deadlines | ✅ tested live |
| CADC International Astronomy Meetings | Worldwide astronomy meetings (via official iCal/RSS feeds) | ✅ parser tested on real feed data |
| ICTS Bengaluru | Programs, schools, discussion meetings, lecture series | ✅ parser tested on real page structure |
| `scraper/manual_events.yaml` | Anything you add by hand | ✅ tested |

CADC's HTML pages are JavaScript-rendered, so the scraper uses CADC's
official structured feeds instead (complete iCal, falling back to RSS) —
far more robust than HTML parsing. Every scraper runs inside `try/except`,
so one broken site never kills the pipeline.

## Customizing

- **Your interests** → edit `INTERESTS` (keywords + weights) and
  `COMBO_BONUS` in `scraper/scrape.py`.
- **Add an institute** → write one function in `scraper/sources.py`
  returning the standard dict, register it in `SOURCES`. IUCAA, IISc APC,
  TIFR, IMSc, ARIES, PRL all follow the same pattern as the ICTS example.
- **Add a one-off event** (poster, email, circular) →
  append to `scraper/manual_events.yaml`.
- **Notification threshold** → the `e["score"] >= 30` line in `scrape.py`.

## Running locally

```bash
pip install -r requirements.txt
python scraper/scrape.py
cd docs && python -m http.server 8000   # open http://localhost:8000
```

## Background

Use the **Appearance** control in the filter rail: Cosmic poster (default,
`docs/bg-cosmos.svg` — spacetime grid, black hole, galaxy, supernova,
satellite, and landmark equations of Einstein, Friedmann, Schrödinger,
Hardy–Ramanujan, FLRW and CPL), Starfield only, **My own image** (picked
from your device, stored locally in your browser only — never uploaded),
or Plain dark. To change the default poster, edit/replace `docs/bg-cosmos.svg`.

## Install as an app (Android / iOS / desktop)

The site is a PWA. On Android Chrome: open the site → ⋮ menu →
**Add to Home screen** → Install. It opens fullscreen with the black-hole
icon and works offline with the last fetched events. For a real `.apk`
(like DG Lab), feed the site URL to https://www.pwabuilder.com → Android
→ download the generated package.
