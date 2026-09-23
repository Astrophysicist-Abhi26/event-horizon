"""
India sources (driven by institutes.yaml) and the manual watchlist.

Each institute page and each Indico server is registered as its OWN source,
so the health panel shows exactly which page is working.
"""

import datetime as dt
import os
import re

import yaml

from common import clean, get, iso, parse_date_range, today
from listing import extract_listing

HERE = os.path.dirname(os.path.abspath(__file__))
INSTITUTES = os.path.join(HERE, "institutes.yaml")
WATCHLIST = os.path.join(HERE, "watchlist.yaml")
INDICO_HORIZON_DAYS = 540


def _load(path):
    try:
        with open(path) as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        return {}


def _page_source(cfg):
    def run():
        return extract_listing(cfg["url"], cfg["name"], cfg.get("location", "India"),
                               href_filter=cfg.get("href_filter"),
                               raw_type=cfg.get("type"))
    return run


def _indico_source(cfg):
    def run():
        frm = today().isoformat()
        to = (today() + dt.timedelta(days=INDICO_HORIZON_DAYS)).isoformat()
        url = f"{cfg['base'].rstrip('/')}/export/categ/{cfg.get('category', 0)}.json"
        data = get(url, params={"from": frm, "to": to, "limit": 500}).json()
        out = []
        for e in data.get("results", []) if isinstance(data, dict) else []:
            title = clean(e.get("title"))
            if not title:
                continue
            loc = clean(e.get("location") or "") or cfg.get("location")
            start = iso(e.get("startDate"))
            out.append(dict(title=title, url=e.get("url") or cfg["base"],
                            start_date=start, end_date=iso(e.get("endDate")) or start,
                            deadline=None, location=loc, country=None, online=False,
                            tz=(e.get("timezone") or None),
                            description=clean(e.get("description"))[:1500],
                            speaker=None, source=cfg["name"],
                            raw_type=e.get("type"), declared=[], priority=False))
        return out
    return run


def india_sources():
    """-> list of (name, fn, min_expected)"""
    cfg = _load(INSTITUTES)
    out = []
    for p in cfg.get("pages") or []:
        out.append((p["name"], _page_source(p), int(p.get("min_expected", 0))))
    for i in cfg.get("indico") or []:
        out.append((i["name"], _indico_source(i), 0))
    return out


# ---------------------------------------------------------------------------
# Manual watchlist — ad-hoc conference microsites no scraper can reach.
# ---------------------------------------------------------------------------
def scrape_watchlist():
    items = _load(WATCHLIST)
    if isinstance(items, dict):
        items = items.get("events") or []
    out = []
    for it in items or []:
        if not isinstance(it, dict) or not it.get("url"):
            continue
        url = str(it["url"]).strip()
        title, start, end = it.get("title"), iso(it.get("start")), iso(it.get("end"))
        if not title or not start:  # URL-only entry: read what we can from the page
            try:
                html = get(url).text
                if not title:
                    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.S | re.I)
                    title = clean(m.group(1)) if m else None
                if not start:
                    start, end = parse_date_range(re.sub(r"<[^>]+>", " ", html)[:20000])
            except Exception as exc:
                print(f"  watchlist fetch failed for {url}: {exc}")
        out.append(dict(
            title=title or url, url=url, start_date=start, end_date=end or start,
            deadline=iso(it.get("deadline")), location=it.get("location"),
            country=it.get("country"), online=bool(it.get("online")), tz=None,
            description=clean(it.get("notes") or ""), speaker=None,
            source="Watchlist", raw_type=it.get("type"),
            declared=[f"field:{x}" for x in it.get("fields") or []],
            priority=True))
    return out
