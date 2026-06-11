"""
Event Horizon — source scrapers.

Every scraper returns a list of dicts with these keys (None where unknown):
    title, url, start_date (YYYY-MM-DD), end_date, deadline,
    location, source, raw_type
Add a new institute by writing one function and registering it in SOURCES
at the bottom of this file. Each scraper is isolated: if one site changes
its HTML or is unreachable, the others still run.
"""

import re
import datetime as dt

import requests
import yaml
from bs4 import BeautifulSoup
from dateutil import parser as dateparser

HEADERS = {
    "User-Agent": "EventHorizon/1.0 (academic event aggregator; personal research use)"
}
TIMEOUT = 30


def _get(url):
    r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    r.raise_for_status()
    return r


def _iso(d):
    """Best-effort parse of a date string -> 'YYYY-MM-DD' or None."""
    if not d:
        return None
    try:
        return dateparser.parse(str(d), fuzzy=True, dayfirst=False).date().isoformat()
    except (ValueError, OverflowError, TypeError):
        return None


# ---------------------------------------------------------------------------
# 1. AI Deadlines (huggingface/ai-deadlines) — actively maintained database of
#    major AI/ML conferences. One YAML file per conference; we download the
#    repository zip in a single request and parse every file.
# ---------------------------------------------------------------------------
def scrape_ai_deadlines():
    import io
    import zipfile

    url = "https://codeload.github.com/huggingface/ai-deadlines/zip/refs/heads/main"
    zf = zipfile.ZipFile(io.BytesIO(_get(url).content))
    events = []
    for name in zf.namelist():
        if "/src/data/conferences/" not in name or not name.endswith((".yml", ".yaml")):
            continue
        try:
            data = yaml.safe_load(zf.read(name)) or []
        except yaml.YAMLError:
            continue
        for c in data:
            title = f"{c.get('title', '')} {c.get('year', '')}".strip()
            full = c.get("full_name")
            if full:
                title = f"{title} — {full}"
            # earliest upcoming paper/abstract deadline, if any
            deadline = None
            for d in c.get("deadlines", []):
                if d.get("type") in ("paper", "abstract"):
                    deadline = deadline or _iso(str(d.get("date", "")).split(" ")[0])
            events.append({
                "title": title,
                "url": c.get("link"),
                "start_date": _iso(c.get("start")),
                "end_date": _iso(c.get("end")),
                "deadline": deadline,
                "location": c.get("place") or c.get("venue") or c.get("city"),
                "source": "AI Deadlines",
                "raw_type": "conference",
                "extra_tags": ["ai-ml"],
            })
    return events


# ---------------------------------------------------------------------------
# 2. CADC International Astronomy Meetings List — the canonical worldwide
#    astronomy meetings list, maintained since the 1990s.
#    Page is a year-by-year list of lines like:
#    "5-9 Jan: <a href=...>AAS 245th Meeting</a>, National Harbor, MD, USA"
# ---------------------------------------------------------------------------
def scrape_cadc_meetings():
    base = "https://www.cadc-ccda.hia-iha.nrc-cnrc.gc.ca/en/meetings/"
    soup = BeautifulSoup(_get(base).text, "html.parser")
    events = []
    year = dt.date.today().year
    # Tolerant parse: walk every link; use surrounding line text for date/place.
    for a in soup.find_all("a", href=True):
        line = a.find_parent(["li", "p", "tr", "div"])
        if line is None:
            continue
        text = " ".join(line.get_text(" ", strip=True).split())
        title = a.get_text(" ", strip=True)
        if not title or len(title) < 6:
            continue
        # Look for a leading date pattern e.g. "5-9 Jan" / "12 Feb - 3 Mar"
        m = re.match(r"^(\d{1,2})\s*[-–]?\s*(\d{1,2})?\s+([A-Za-z]{3,9})", text)
        ym = re.search(r"\b(20\d\d)\b", text)
        if ym:
            year = int(ym.group(1))
        start = end = None
        if m:
            day1, day2, month = m.group(1), m.group(2), m.group(3)
            start = _iso(f"{day1} {month} {year}")
            end = _iso(f"{day2} {month} {year}") if day2 else start
        if not start:
            continue
        # Location: text after the link
        after = text.split(title, 1)[-1].strip(" ,:;-")
        events.append({
            "title": title,
            "url": requests.compat.urljoin(base, a["href"]),
            "start_date": start,
            "end_date": end,
            "deadline": None,
            "location": after or None,
            "source": "CADC Astronomy Meetings",
            "raw_type": None,
            "extra_tags": ["astro"],
        })
    return events


# ---------------------------------------------------------------------------
# 3. ICTS Bengaluru — programs/discussion meetings/schools
# ---------------------------------------------------------------------------
def scrape_icts():
    base = "https://www.icts.res.in"
    soup = BeautifulSoup(_get(base + "/program").text, "html.parser")
    events = []
    for a in soup.select("a[href*='/program/'], a[href*='/discussion-meeting/'], a[href*='/school/']"):
        title = a.get_text(" ", strip=True)
        if not title or len(title) < 8:
            continue
        block = a.find_parent(["div", "li", "article", "tr"])
        text = block.get_text(" ", strip=True) if block else ""
        m = re.search(
            r"(\d{1,2}\s+[A-Za-z]{3,9}\s+20\d\d)\s*(?:to|–|-)\s*(\d{1,2}\s+[A-Za-z]{3,9}\s+20\d\d)?",
            text,
        )
        start = _iso(m.group(1)) if m else None
        end = _iso(m.group(2)) if (m and m.group(2)) else start
        events.append({
            "title": title,
            "url": requests.compat.urljoin(base, a["href"]),
            "start_date": start,
            "end_date": end,
            "deadline": None,
            "location": "ICTS, Bengaluru, India",
            "source": "ICTS Bengaluru",
            "raw_type": None,
            "extra_tags": ["astro", "physics", "math"],
        })
    return events


# ---------------------------------------------------------------------------
# 4. Manual events — anything you add by hand in scraper/manual_events.yaml
#    (e.g. RRI's "Symphony of Spacetime", department circulars, emails)
# ---------------------------------------------------------------------------
def scrape_manual():
    import os
    path = os.path.join(os.path.dirname(__file__), "manual_events.yaml")
    if not os.path.exists(path):
        return []
    with open(path) as f:
        data = yaml.safe_load(f) or []
    events = []
    for c in data:
        events.append({
            "title": c.get("title"),
            "url": c.get("url"),
            "start_date": _iso(c.get("start")),
            "end_date": _iso(c.get("end")) or _iso(c.get("start")),
            "deadline": _iso(c.get("deadline")),
            "location": c.get("location"),
            "source": c.get("source", "Manual"),
            "raw_type": c.get("type"),
            "extra_tags": c.get("tags", []),
        })
    return events


# Registry: (name, function). Comment a line out to disable a source.
SOURCES = [
    ("AI Deadlines", scrape_ai_deadlines),
    ("CADC Astronomy Meetings", scrape_cadc_meetings),
    ("ICTS Bengaluru", scrape_icts),
    ("Manual", scrape_manual),
]
