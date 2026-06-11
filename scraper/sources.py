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
#    astronomy meetings list. The HTML pages are JavaScript-rendered (so
#    plain requests sees nothing), but CADC publishes structured feeds:
#    a complete iCal and an RSS of recent additions. We try iCal first,
#    then fall back to RSS. No HTML parsing needed.
# ---------------------------------------------------------------------------
CADC_ICS = "https://ws-cadc.canfar.net/vault/files/dbohlender/CADC/astroMeetings.ics"
CADC_RSS = "https://www.cadc-ccda.hia-iha.nrc-cnrc.gc.ca/meetings/rssFeed"


def _parse_cadc_ics(text):
    """Minimal tolerant iCal parser: unfold lines, read VEVENT blocks."""
    lines, out = [], []
    for raw in text.splitlines():
        if raw[:1] in (" ", "\t") and lines:      # folded continuation line
            lines[-1] += raw[1:]
        else:
            lines.append(raw.rstrip("\r"))
    ev = None
    for ln in lines:
        if ln == "BEGIN:VEVENT":
            ev = {}
        elif ln == "END:VEVENT" and ev is not None:
            out.append(ev)
            ev = None
        elif ev is not None and ":" in ln:
            key, val = ln.split(":", 1)
            key = key.split(";")[0].upper()
            ev[key] = val.replace("\\,", ",").replace("\\n", " ").strip()
    events = []
    for ev in out:
        title = ev.get("SUMMARY")
        if not title:
            continue
        url = ev.get("URL")
        if not url:  # often the link hides in DESCRIPTION
            m = re.search(r"https?://\S+", ev.get("DESCRIPTION", ""))
            url = m.group(0).rstrip(").,") if m else None
        events.append({
            "title": title,
            "url": url or CADC_RSS,
            "start_date": _iso(ev.get("DTSTART", "")[:8]),
            "end_date": _iso(ev.get("DTEND", "")[:8]),
            "deadline": None,
            "location": ev.get("LOCATION"),
            "source": "CADC Astronomy Meetings",
            "raw_type": None,
            "extra_tags": ["astro"],
        })
    return events


def _parse_cadc_rss(text):
    """RSS items carry an HTML table in <description> with Date/Location."""
    import html
    import xml.etree.ElementTree as ET
    root = ET.fromstring(text)
    events = []
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        desc = html.unescape(item.findtext("description") or "")
        if not title:
            continue
        m = re.search(
            r"Date.*?(\w+ \d{1,2}, \w+ \d{4})(?:\s*to\s*(\w+ \d{1,2}, \w+ \d{4}))?",
            desc,
        )
        start = _iso(m.group(1)) if m else None
        end = _iso(m.group(2)) if (m and m.group(2)) else start
        lm = re.search(r"Location</TD><TD>([^<]*)", desc, re.I)
        events.append({
            "title": title,
            "url": link or CADC_RSS,
            "start_date": start,
            "end_date": end,
            "deadline": None,
            "location": lm.group(1).strip() if lm else None,
            "source": "CADC Astronomy Meetings",
            "raw_type": None,
            "extra_tags": ["astro"],
        })
    return events


def scrape_cadc_meetings():
    try:
        events = _parse_cadc_ics(_get(CADC_ICS).text)
        if events:
            return events
    except Exception as exc:
        print(f"  CADC iCal unavailable ({exc}); falling back to RSS")
    return _parse_cadc_rss(_get(CADC_RSS).text)


# ---------------------------------------------------------------------------
# 3. ICTS Bengaluru — programs/discussion meetings/schools/lecture series.
#    Correct listing pages (verified June 2026): /programs/upcoming and
#    /current-and-upcoming-events. Event links live under /program/,
#    /discussion-meeting/, /event/, /lectures/, /school/. Dates appear as
#    "06 July 2026 to 10 July 2026".
# ---------------------------------------------------------------------------
ICTS_URLS = [
    "https://www.icts.res.in/programs/upcoming",
    "https://www.icts.res.in/current-and-upcoming-events",
]
ICTS_HREF = re.compile(
    r"/(program|discussion-meeting|event|lectures|school|summer-course)", re.I)
ICTS_DATE = re.compile(
    r"(\d{1,2}\s+[A-Za-z]{3,9}\s+20\d\d)\s*(?:to|–|-)?\s*(\d{1,2}\s+[A-Za-z]{3,9}\s+20\d\d)?")
ICTS_TYPE = {"program": "workshop", "discussion-meeting": "workshop",
             "lectures": "lecture series", "school": "school",
             "summer-course": "lecture series", "event": "conference"}


def scrape_icts():
    base = "https://www.icts.res.in"
    events, seen_urls = [], set()
    for list_url in ICTS_URLS:
        try:
            soup = BeautifulSoup(_get(list_url).text, "html.parser")
        except Exception as exc:
            print(f"  ICTS list {list_url} failed ({exc})")
            continue
        for a in soup.find_all("a", href=True):
            href = a["href"]
            m = ICTS_HREF.search(href)
            title = a.get_text(" ", strip=True)
            if not m or not title or len(title) < 8:
                continue
            url = requests.compat.urljoin(base, href)
            if url in seen_urls:
                continue
            block = a.find_parent(["div", "li", "article", "tr", "td"])
            text = block.get_text(" ", strip=True) if block else ""
            dm = ICTS_DATE.search(text)
            if not dm:  # try one level higher before giving up on dates
                parent = block.parent if block is not None else None
                if parent is not None:
                    dm = ICTS_DATE.search(parent.get_text(" ", strip=True))
            start = _iso(dm.group(1)) if dm else None
            end = _iso(dm.group(2)) if (dm and dm.group(2)) else start
            seen_urls.add(url)
            events.append({
                "title": title,
                "url": url,
                "start_date": start,
                "end_date": end,
                "deadline": None,
                "location": "ICTS, Bengaluru, India",
                "source": "ICTS Bengaluru",
                "raw_type": ICTS_TYPE.get(m.group(1).lower(), None),
                "extra_tags": ["astro", "physics", "math"],
            })
    return events


# ---------------------------------------------------------------------------
# 5. researchseminars.org — the global registry of academic seminars/talks
#    (born at MIT, 2020). Clean JSON API; we pull upcoming talks in a
#    3-week window and keep math/physics/CS/statistics ones.
# ---------------------------------------------------------------------------
RS_API = "https://researchseminars.org/api/0/search/talks"
RS_KEEP_PREFIXES = ("math", "physics", "astro", "cs", "stat")
RS_WINDOW_DAYS = 21
RS_MAX_TALKS = 250


def _rs_tags(topics):
    tags = set()
    for t in topics or []:
        t = t.lower()
        if t.startswith("math"):
            tags.add("math")
        if t.startswith("physics") or "astro" in t:
            tags.add("physics")
        if "astro" in t or "gr-qc" in t or "cosmo" in t:
            tags.add("astro")
        if t.startswith(("cs", "stat")) or "machine" in t or "_ml" in t:
            tags.add("ai-ml")
    return sorted(tags)


def scrape_researchseminars():
    import json as _json
    today = dt.date.today()
    horizon = today + dt.timedelta(days=RS_WINDOW_DAYS)
    query = {
        "start_time": {"$gte": today.isoformat(),
                       "$lte": horizon.isoformat() + "T23:59:59"},
    }
    params = {k: _json.dumps(v) for k, v in query.items()}
    r = requests.get(RS_API, params=params, headers=HEADERS, timeout=TIMEOUT)
    r.raise_for_status()
    results = r.json().get("results", [])
    events = []
    for t in results:
        topics = t.get("topics") or []
        if not any(str(tp).lower().startswith(RS_KEEP_PREFIXES) for tp in topics):
            continue
        title = (t.get("title") or "").strip()
        if not title or title.upper() == "TBA":
            continue
        speaker = (t.get("speaker") or "").strip()
        if speaker:
            title = f"{title} — {speaker}"
        sid, ctr = t.get("seminar_id"), t.get("seminar_ctr")
        url = (f"https://researchseminars.org/talk/{sid}/{ctr}/"
               if sid and ctr is not None else "https://researchseminars.org/")
        start = _iso(str(t.get("start_time", ""))[:10])
        end = _iso(str(t.get("end_time", ""))[:10]) or start
        loc = "Online" if t.get("online") else (t.get("speaker_affiliation") or None)
        events.append({
            "title": title,
            "url": url,
            "start_date": start,
            "end_date": end,
            "deadline": None,
            "location": loc,
            "source": "researchseminars.org",
            "raw_type": "seminar",
            "extra_tags": _rs_tags(topics),
        })
        if len(events) >= RS_MAX_TALKS:
            break
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
    ("researchseminars.org", scrape_researchseminars),
    ("Manual", scrape_manual),
]
