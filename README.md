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
| huggingface/ai-deadlines | All major AI/ML conferences + deadlines | ✅ tested |
| CADC International Astronomy Meetings | Worldwide astronomy meetings list | ⚠️ verify after first Action run |
| ICTS Bengaluru | Programs, schools, discussion meetings | ⚠️ verify after first Action run |
| `scraper/manual_events.yaml` | Anything you add by hand | ✅ tested |

The CADC and ICTS scrapers could not be network-tested in the build
environment; they run inside `try/except`, so if either site changed its
HTML the rest of the pipeline is unaffected. Check the Action log after the
first run and adjust the parser if needed.

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
