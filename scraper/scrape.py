"""
Event Horizon — main pipeline.

Runs every source scraper, normalizes and deduplicates events, classifies
event type and country, scores relevance against your research interests,
and writes:
    docs/events.json      full database the website reads
    new_events.md         human-readable list of newly discovered events
                          (used by the GitHub Action to open an Issue,
                          which triggers an email notification to you)

Run locally:  python scraper/scrape.py
"""

import datetime as dt
import hashlib
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
from sources import SOURCES  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EVENTS_PATH = os.path.join(ROOT, "docs", "events.json")
NEW_PATH = os.path.join(ROOT, "new_events.md")

# ---------------------------------------------------------------------------
# Your interest profile. Edit weights/keywords freely — score is capped at 100.
# ---------------------------------------------------------------------------
INTERESTS = {
    "astro": (40, [
        "astronom", "astrophys", "cosmolog", "dark energy", "dark matter",
        "supernova", "galax", "black hole", "gravitational", "cmb",
        "large-scale structure", "bao", "desi", "lsst", "ztf", "transient",
        "time-domain", "exoplanet", "stellar", "pulsar", "neutron star",
        "21 cm", "21cm", "reionization", "spacetime", "relativity",
    ]),
    "ai-ml": (35, [
        "machine learning", "deep learning", "neural", "artificial intelligence",
        " ai ", "ai for", "ai in", "data science", "bayesian", "inference",
        "statistic", "kolmogorov", "computer vision", "nlp", "learning theory",
        "representation learning", "generative", "foundation model",
        "simulation-based", "sbi", "uncertainty quantification",
    ]),
    "physics": (20, [
        "physics", "quantum", "string", "particle", "high energy",
        "field theory", "plasma", "solar", "heliophys", "condensed matter",
    ]),
    "math": (20, [
        "mathematic", "number theory", "topolog", "geometry", "algebra",
        "analysis", "probability", "signal processing", "compressed sensing",
        "information theory",
    ]),
}
COMBO_BONUS = 25  # events at the astro × AI/ML intersection get a boost

TYPE_RULES = [
    ("school", "School"),
    ("lecture series", "Lecture series"),
    ("workshop", "Workshop"),
    ("symposium", "Conference"),
    ("conference", "Conference"),
    ("colloquium", "Talk / Seminar"),
    ("seminar", "Talk / Seminar"),
    ("talk", "Talk / Seminar"),
    ("meeting", "Conference"),
    ("hackathon", "Workshop"),
    ("program", "Workshop"),
]

COUNTRIES = [
    "India", "USA", "United States", "UK", "United Kingdom", "Germany",
    "France", "Italy", "Spain", "Netherlands", "Switzerland", "Austria",
    "Belgium", "Sweden", "Norway", "Denmark", "Finland", "Poland", "Portugal",
    "Greece", "Ireland", "Czech", "Hungary", "Japan", "China", "South Korea",
    "Korea", "Taiwan", "Singapore", "Australia", "New Zealand", "Canada",
    "Mexico", "Brazil", "Argentina", "Chile", "South Africa", "Israel",
    "Turkey", "Russia", "UAE", "Saudi Arabia", "Thailand", "Vietnam",
    "Indonesia", "Malaysia", "Online", "Virtual",
]
US_STATE_HINT = re.compile(r",\s*[A-Z]{2}\b")  # "Phoenix, AZ" style

CITY_HINTS = {
    "bengaluru": "India", "bangalore": "India", "mumbai": "India", "pune": "India",
    "delhi": "India", "chennai": "India", "kolkata": "India", "hyderabad": "India",
    "maastricht": "Netherlands", "amsterdam": "Netherlands", "vienna": "Austria",
    "paris": "France", "lyon": "France", "berlin": "Germany", "munich": "Germany",
    "heidelberg": "Germany", "garching": "Germany", "zurich": "Switzerland",
    "geneva": "Switzerland", "london": "UK", "oxford": "UK", "cambridge, uk": "UK",
    "edinburgh": "UK", "rome": "Italy", "milan": "Italy", "trieste": "Italy",
    "madrid": "Spain", "barcelona": "Spain", "lisbon": "Portugal",
    "stockholm": "Sweden", "copenhagen": "Denmark", "helsinki": "Finland",
    "prague": "Czech", "budapest": "Hungary", "warsaw": "Poland",
    "athens": "Greece", "dublin": "Ireland", "tokyo": "Japan", "kyoto": "Japan",
    "beijing": "China", "shanghai": "China", "seoul": "South Korea",
    "taipei": "Taiwan", "sydney": "Australia", "melbourne": "Australia",
    "vancouver": "Canada", "toronto": "Canada", "montreal": "Canada",
    "montréal": "Canada", "santiago": "Chile", "cape town": "South Africa",
    "tel aviv": "Israel", "istanbul": "Turkey", "abu dhabi": "UAE",
    "dubai": "UAE", "san diego": "USA", "new york": "USA", "boston": "USA",
    "seattle": "USA", "san francisco": "USA", "nashville": "USA",
    "honolulu": "USA", "rio de janeiro": "Brazil",
}



def classify_type(title, raw_type):
    text = f"{raw_type or ''} {title or ''}".lower()
    for key, label in TYPE_RULES:
        if key in text:
            return label
    return "Conference"  # most aggregated listings are conferences


def detect_country(location):
    if not location:
        return None
    loc = location.lower()
    for c in COUNTRIES:
        if c.lower() in loc:
            if c in ("United States",):
                return "USA"
            if c in ("United Kingdom",):
                return "UK"
            if c in ("Virtual",):
                return "Online"
            if c == "Korea":
                return "South Korea"
            return c
    if US_STATE_HINT.search(location):
        return "USA"
    for city, country in CITY_HINTS.items():
        if city in loc:
            return country
    return None


def score_event(title, location, extra_tags):
    text = f" {title or ''} {location or ''} ".lower()
    score, tags = 0, set(extra_tags or [])
    for tag, (weight, kws) in INTERESTS.items():
        hits = sum(1 for k in kws if k in text)
        if hits:
            tags.add(tag)
            score += weight + min(hits - 1, 3) * 5
    # tags injected by the source (e.g. everything from CADC is astro)
    for tag in (extra_tags or []):
        if tag in INTERESTS:
            score += INTERESTS[tag][0] // 2
    if "astro" in tags and "ai-ml" in tags:
        score += COMBO_BONUS
    return min(score, 100), sorted(tags)


def event_id(e):
    key = f"{e['title']}|{e.get('start_date')}|{e.get('source')}"
    return hashlib.sha1(key.encode()).hexdigest()[:12]


def main():
    today = dt.date.today().isoformat()
    all_events, errors = [], []

    for name, fn in SOURCES:
        try:
            batch = fn()
            print(f"[ok]   {name}: {len(batch)} events")
            all_events.extend(batch)
        except Exception as exc:  # one broken site must not kill the run
            errors.append(f"{name}: {exc}")
            print(f"[fail] {name}: {exc}")

    # Normalize, score, dedupe
    seen, out = set(), []
    for e in all_events:
        if not e.get("title") or not e.get("url"):
            continue
        # Drop events that ended in the past (keep undated ones)
        end = e.get("end_date") or e.get("start_date")
        if end and end < today:
            continue
        score, tags = score_event(e["title"], e.get("location"), e.get("extra_tags"))
        country = detect_country(e.get("location"))
        rec = {
            "id": None,
            "title": e["title"].strip(),
            "url": e["url"],
            "start_date": e.get("start_date"),
            "end_date": e.get("end_date") or e.get("start_date"),
            "deadline": e.get("deadline"),
            "location": e.get("location"),
            "country": country,
            "in_india": country == "India",
            "type": classify_type(e["title"], e.get("raw_type")),
            "source": e.get("source"),
            "score": score,
            "tags": tags,
        }
        rec["id"] = event_id(rec)
        if rec["id"] in seen:
            continue
        seen.add(rec["id"])
        out.append(rec)

    out.sort(key=lambda r: (r["start_date"] or "9999", -r["score"]))

    # Diff against previous run to find NEW events worth notifying about
    old_ids = set()
    if os.path.exists(EVENTS_PATH):
        try:
            with open(EVENTS_PATH) as f:
                old_ids = {e["id"] for e in json.load(f).get("events", [])}
        except Exception:
            pass
    new = [e for e in out if e["id"] not in old_ids and e["score"] >= 30]

    os.makedirs(os.path.dirname(EVENTS_PATH), exist_ok=True)
    with open(EVENTS_PATH, "w") as f:
        json.dump(
            {"generated": dt.datetime.now(dt.timezone.utc).isoformat(),
             "errors": errors, "events": out},
            f, indent=1,
        )
    print(f"\nWrote {len(out)} events -> docs/events.json")

    if new and old_ids:  # skip notification on the very first run
        lines = [f"## {len(new)} new event(s) matching your interests (score ≥ 30)\n"]
        for e in sorted(new, key=lambda r: -r["score"]):
            lines.append(
                f"- **[{e['title']}]({e['url']})** — {e['type']}, "
                f"{e['location'] or 'location TBA'}, "
                f"{e['start_date'] or 'date TBA'} · relevance {e['score']}%"
            )
        with open(NEW_PATH, "w") as f:
            f.write("\n".join(lines))
        print(f"Wrote {len(new)} new events -> new_events.md")
    elif os.path.exists(NEW_PATH):
        os.remove(NEW_PATH)


if __name__ == "__main__":
    main()
