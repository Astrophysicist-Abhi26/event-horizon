"""
India sources — driven by scraper/institutes.yaml — plus the two manual
channels: the watchlist file and "Add event" GitHub issues.

Every registry entry becomes its OWN source (own line in the health panel),
and picks one of five adapters with `kind:`

  listing          any HTML page that lists upcoming events (generic extractor)
  ical             any public iCal feed (.ics)
  google_calendar  a public Google Calendar, by calendar id
  wp_events        WordPress "The Events Calendar" sites (REST API, iCal fallback)
  indico           an Indico server (JSON export API)

Structured feeds (ical / google_calendar / wp_events / indico) are preferred
whenever an institute offers one: they do not break when a page is redesigned.
"""

import datetime as dt
import os
import re

import yaml

from common import (clean, first_url, get, ics_end_date, iso, parse_date_range,
                    parse_ics, today)
from listing import extract_listing

HERE = os.path.dirname(os.path.abspath(__file__))
INSTITUTES = os.path.join(HERE, "institutes.yaml")
WATCHLIST = os.path.join(HERE, "watchlist.yaml")
INDICO_HORIZON_DAYS = 540
ICAL_HORIZON_DAYS = 400
RECUR_WINDOW_DAYS = 45       # recurring calendar series: only the next few weeks
RECUR_MAX = 3


def _load(path):
    try:
        with open(path) as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        return {}


def _urls(cfg):
    """`url` or `urls`, with {year} / {next_year} filled in (for pages such as
    .../Seminars{year}.html that move every January)."""
    raw = cfg.get("urls") or [cfg["url"]]
    y = today().year
    out = []
    for u in raw:
        for yy in ([y, y + 1] if "{year}" in u and today().month >= 11 else [y]):
            out.append(u.format(year=yy, next_year=yy + 1))
    return list(dict.fromkeys(out))


def _event(cfg, title, url, start, end=None, location=None, description="",
           raw_type=None, speaker=None, online=False, tz=None):
    return dict(title=clean(title), url=url, start_date=start, end_date=end or start,
                deadline=None, location=clean(location) or cfg.get("location"),
                country=None, online=online, tz=tz,
                description=clean(description)[:1500], speaker=speaker,
                source=cfg["name"], raw_type=raw_type or cfg.get("type"),
                declared=[], priority=False)


# ---------------------------------------------------------------------------
# listing — generic HTML extractor
# ---------------------------------------------------------------------------
def _listing(cfg):
    out = []
    for url in _urls(cfg):
        out += extract_listing(url, cfg["name"], cfg.get("location", "India"),
                               href_filter=cfg.get("href_filter"),
                               raw_type=cfg.get("type"),
                               insecure_ok=bool(cfg.get("insecure_ok")))
    return out


# ---------------------------------------------------------------------------
# ical / google_calendar
# ---------------------------------------------------------------------------
def _gcal_url(cal_id):
    return (f"https://calendar.google.com/calendar/ical/"
            f"{cal_id.replace('@', '%40')}/public/basic.ics")


def _expand(ev, start):
    """Upcoming occurrences of a recurring (RRULE) event, capped."""
    from dateutil.rrule import rrulestr
    try:
        rule = rrulestr(ev["RRULE"], dtstart=dt.datetime.fromisoformat(start))
    except (ValueError, TypeError):
        return []
    lo = dt.datetime.combine(today(), dt.time())
    hi = lo + dt.timedelta(days=RECUR_WINDOW_DAYS)
    return [d.date().isoformat() for d in rule.between(lo, hi, inc=True)][:RECUR_MAX]


def ical_events(cfg, text):
    calname = re.search(r"^X-WR-CALNAME:(.+)$", text, re.M)
    calname = clean(calname.group(1)) if calname else ""
    t = today().isoformat()
    horizon = (today() + dt.timedelta(days=ICAL_HORIZON_DAYS)).isoformat()
    out = []
    for ev in parse_ics(text):
        title = clean(ev.get("SUMMARY"))
        start = iso(ev.get("DTSTART"))
        if not title or not start or ev.get("STATUS", "").upper() == "CANCELLED":
            continue
        all_day = len(re.sub(r"\D", "", ev.get("DTSTART", ""))) == 8
        end = ics_end_date(start, ev.get("DTEND"), all_day)
        starts = _expand(ev, start) if ev.get("RRULE") else [start]
        desc = clean(ev.get("DESCRIPTION"))
        url = ev.get("URL") or first_url(desc) or cfg.get("page") or cfg.get("url")
        loc = ev.get("LOCATION") or ""
        for s in starts:
            if s > horizon or (end if s == start else s) < t:
                continue
            e = end if s == start else s
            out.append(_event(cfg, title, url, s, e, cfg.get("location"),
                              description=" · ".join(x for x in (calname, loc, desc) if x),
                              online=bool(re.search(r"zoom|meet\.google|teams", loc, re.I))))
    return out


def _ical(cfg):
    out = []
    for url in _urls(cfg):
        out += ical_events(cfg, get(url, insecure_ok=bool(cfg.get("insecure_ok"))).text)
    return out


def _google_calendar(cfg):
    ids = cfg.get("calendars") or [cfg["calendar"]]
    out, errors = [], []
    for cal in ids:
        try:
            out += ical_events(cfg, get(_gcal_url(cal)).text)
        except Exception as exc:        # one private calendar must not hide the rest
            errors.append(f"{cal[:12]}…: {exc.__class__.__name__}")
    if errors and not out:
        raise RuntimeError("; ".join(errors))
    return out


# ---------------------------------------------------------------------------
# wp_events — WordPress "The Events Calendar" (tribe) sites
# ---------------------------------------------------------------------------
def wp_events_from_json(cfg, data):
    out = []
    for e in data.get("events") or []:
        venue = e.get("venue") if isinstance(e.get("venue"), dict) else {}
        loc = ", ".join(x for x in (venue.get("venue"), venue.get("city")) if x) or None
        cats = [c.get("name", "") for c in e.get("categories") or [] if isinstance(c, dict)]
        out.append(_event(cfg, e.get("title"), e.get("url") or cfg["base"],
                          iso(e.get("start_date")), iso(e.get("end_date")), loc,
                          description=e.get("description") or e.get("excerpt") or "",
                          raw_type=" ".join(cats) or None))
    return out


def _wp_events(cfg):
    base = cfg["base"].rstrip("/")
    insecure = bool(cfg.get("insecure_ok"))
    try:
        url = f"{base}/wp-json/tribe/events/v1/events"
        params = {"start_date": today().isoformat(), "per_page": 50,
                  "end_date": (today() + dt.timedelta(days=ICAL_HORIZON_DAYS)).isoformat()}
        out = []
        for _ in range(4):                               # at most 200 events
            data = get(url, params=params, insecure_ok=insecure).json()
            out += wp_events_from_json(cfg, data)
            url, params = data.get("next_rest_url"), None
            if not url:
                break
        return out
    except Exception:
        # REST API switched off on some sites -> the plugin's iCal export
        text = get(f"{base}/{cfg.get('events_path', 'events').strip('/')}/?ical=1",
                   insecure_ok=insecure).text
        return ical_events(cfg, text)


# ---------------------------------------------------------------------------
# indico
# ---------------------------------------------------------------------------
def _indico(cfg):
    """JSON export first; many servers (IIA, since 2026) now demand an API key
    for it, so fall back to the category's public iCal feed, which does not."""
    frm = today().isoformat()
    to = (today() + dt.timedelta(days=INDICO_HORIZON_DAYS)).isoformat()
    cats = cfg.get("categories") or [cfg.get("category", 0)]
    base = cfg["base"].rstrip("/")
    insecure = bool(cfg.get("insecure_ok"))
    out = []
    for cat in cats:
        try:
            data = get(f"{base}/export/categ/{cat}.json",
                       params={"from": frm, "to": to, "limit": 500},
                       insecure_ok=insecure).json()
            if not isinstance(data, dict) or "results" not in data:
                raise ValueError("no results in Indico export")
        except Exception:
            text = get(f"{base}/category/{cat}/events.ics", insecure_ok=insecure).text
            out += ical_events(dict(cfg, page=f"{base}/category/{cat}/"), text)
            continue
        for e in data["results"]:
            start = iso(e.get("startDate"))
            out.append(_event(cfg, e.get("title"), e.get("url") or base, start,
                              iso(e.get("endDate")),
                              clean(e.get("location") or e.get("room") or ""),
                              description=e.get("description") or "",
                              raw_type=e.get("type"), tz=e.get("timezone")))
    return [e for e in out if e["title"]]


ADAPTERS = {"listing": _listing, "ical": _ical, "google_calendar": _google_calendar,
            "wp_events": _wp_events, "indico": _indico}


def _registry(include_disabled=False):
    cfg = _load(INSTITUTES)
    entries = list(cfg.get("sources") or [])
    # v5 layout, still accepted
    entries += [dict(p, kind="listing") for p in cfg.get("pages") or []]
    entries += [dict(i, kind="indico") for i in cfg.get("indico") or []]
    if not include_disabled:
        entries = [e for e in entries if e.get("enabled", True)]
    return entries


def india_sources(include_disabled=False):
    """-> list of (name, fn, min_expected)"""
    out = []
    for e in _registry(include_disabled):
        kind = e.get("kind", "listing")
        if kind not in ADAPTERS:
            raise ValueError(f"institutes.yaml: unknown kind '{kind}' for {e.get('name')}")
        out.append((e["name"], (lambda c=e, f=ADAPTERS[kind]: f(c)),
                    int(e.get("min_expected", 0))))
    return out


# ---------------------------------------------------------------------------
# Manual channel 1: watchlist.yaml (permanent entries, edited by you)
# ---------------------------------------------------------------------------
def _manual_event(it, source):
    url = str(it.get("url") or "").strip()
    title, start, end = it.get("title"), iso(it.get("start")), iso(it.get("end"))
    if url and (not title or not start):   # URL-only entry: read what we can from the page
        try:
            html = get(url).text
            if not title:
                m = re.search(r"<title[^>]*>(.*?)</title>", html, re.S | re.I)
                title = clean(m.group(1)) if m else None
            if not start:
                start, end = parse_date_range(re.sub(r"<[^>]+>", " ", html)[:20000])
        except Exception as exc:
            print(f"  {source}: fetch failed for {url}: {exc}")
    if not url:     # poster/email-only event: link to where it was recorded
        repo = os.environ.get("GITHUB_REPOSITORY", "Astrophysicist-Abhi26/event-horizon")
        url = f"https://github.com/{repo}/blob/main/scraper/watchlist.yaml"
    return dict(
        title=title or url, url=url, start_date=start, end_date=end or start,
        deadline=iso(it.get("deadline")), location=it.get("location"),
        country=it.get("country"), online=bool(it.get("online")), tz=None,
        description=clean(it.get("notes") or ""), speaker=None,
        source=source, raw_type=it.get("type"),
        declared=[f"field:{x}" for x in it.get("fields") or []],
        priority=True)


def scrape_watchlist():
    items = _load(WATCHLIST)
    if isinstance(items, dict):
        items = items.get("events") or []
    return [_manual_event(it, "Watchlist") for it in items or []
            if isinstance(it, dict) and (it.get("url") or it.get("title"))]


# ---------------------------------------------------------------------------
# Manual channel 2: "Add event" GitHub issues (phone-friendly, no commits)
# ---------------------------------------------------------------------------
INTAKE_LABEL = "add-event"
_FIELD_KEYS = {
    "event name": "title", "title": "title", "link": "url", "url": "url",
    "start date": "start", "end date": "end", "deadline": "deadline",
    "registration / abstract deadline": "deadline", "where": "location",
    "location": "location", "type": "type", "fields": "fields",
    "research fields": "fields", "notes": "notes",
}
_FIELD_IDS = {
    "dark energy": "cosmo.de", "large-scale structure": "cosmo.lss",
    "cmb": "cosmo.early", "early universe": "cosmo.early", "dark matter": "cosmo.dm",
    "cosmology": "cosmo.general", "astrophysics": "astro.general",
    "gravitational": "astro.he", "ml for science": "ai.science",
    "ml theory": "ai.theory", "ai": "ai.general", "machine learning": "ai.general",
    "mathematics": "math.other", "number theory": "math.nt", "topology": "math.topology",
    "algebra": "math.algebra", "geometry": "math.geometry",
    "probability": "math.probability", "statistics": "math.probability",
    "mathematical physics": "math.mathphys", "general relativity": "phys.gr",
    "gravitation": "phys.gr", "high-energy": "phys.hepth", "qft": "phys.hepth",
    "physics": "phys.general",
}


def parse_issue_form(title, body):
    """GitHub issue-form body ('### Label\\n\\nvalue') -> watchlist-style dict."""
    it = {}
    for label, value in re.findall(r"^###\s+(.+?)\s*\n+(.*?)(?=^###\s|\Z)", body or "",
                                   re.S | re.M):
        key = _FIELD_KEYS.get(label.strip().lower())
        value = value.strip()
        if not key or not value or value == "_No response_":
            continue
        if key == "fields":
            chosen = re.findall(r"- \[[xX]\]\s*(.+)", value) or re.split(r",\s*", value)
            ids = []
            for c in chosen:
                for k, v in _FIELD_IDS.items():
                    if k in c.lower() and v not in ids:
                        ids.append(v)
                        break
            it["fields"] = ids
        elif key in ("start", "end", "deadline"):
            it[key] = parse_date_range(value)[0] or iso(value)
        else:
            it[key] = value
    if not it.get("title"):
        it["title"] = re.sub(r"^\s*\[?(event|add event)\]?\s*[:\-–]?\s*", "", title or "",
                             flags=re.I).strip() or None
    return it


def scrape_issue_intake():
    repo = os.environ.get("GITHUB_REPOSITORY")
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not repo:
        return []                       # local run: nothing to read
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    issues = get(f"https://api.github.com/repos/{repo}/issues",
                 params={"labels": INTAKE_LABEL, "state": "open", "per_page": 100},
                 headers=headers).json()
    out = []
    for iss in issues if isinstance(issues, list) else []:
        it = parse_issue_form(iss.get("title"), iss.get("body"))
        if not it.get("url"):
            it["url"] = iss.get("html_url")   # poster-only events: the issue holds the poster
        ev = _manual_event(it, "Added by you")
        ev["description"] = (ev["description"] + f" (issue #{iss.get('number')})").strip()
        out.append(ev)
    return out
