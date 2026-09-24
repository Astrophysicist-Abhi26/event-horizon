"""
Event Horizon v5 — global sources.

Every source returns a list of raw event dicts:
    title, url, start_date, end_date, deadline, location, country, online,
    tz, description, speaker, source, raw_type, declared, priority
Unknown values are None / [] / False. Scrapers never tag fields themselves:
they pass through the subject codes the ORGANISERS declared ("declared"),
and taxonomy/classify decide the fields centrally.
"""

import datetime as dt
import io
import json
import re
import xml.etree.ElementTree as ET
import zipfile

import yaml
from bs4 import BeautifulSoup

from common import (clean, first_url, get, ics_end_date, iso,
                    parse_date_range, parse_ics, polite_sleep, today)


def ev(**kw):
    base = dict(title=None, url=None, start_date=None, end_date=None, deadline=None,
                location=None, country=None, online=False, tz=None, description="",
                speaker=None, source=None, raw_type=None, declared=[], priority=False)
    base.update(kw)
    return base


# ---------------------------------------------------------------------------
# 1. AI Deadlines (huggingface/ai-deadlines) — allow-listed venues only
# ---------------------------------------------------------------------------
AID_ZIP = "https://codeload.github.com/huggingface/ai-deadlines/zip/refs/heads/main"
# file stem -> extra declared codes. Venues not listed here are skipped
# (robotics, graphics, HCI, web/IR, document analysis ... are not your field).
AI_VENUES = {
    # learning theory / probabilistic ML
    "colt": ["learning_theory"], "alt": ["learning_theory"],
    "aistats": ["stat_ml"], "uai": ["stat_ml"], "cpal": ["stat_ml"],
    "mathai": ["stat_ml", "mathematics"],
    # core ML
    "neurips": ["machine_learning"], "icml": ["machine_learning"],
    "iclr": ["machine_learning"], "aaai": ["machine_learning"],
    "ijcai": ["machine_learning"], "rlc": ["reinforcement_learning"],
    "collas": ["machine_learning"], "ecml_pkdd": ["machine_learning"],
    "kdd": ["machine_learning"], "esann": ["machine_learning"],
    # adjacent, still useful
    "cvpr": ["computer_vision"], "iccv": ["computer_vision"],
    "eccv": ["computer_vision"], "acl": ["natural_language_processing"],
    "emnlp": ["natural_language_processing"], "naacl": ["natural_language_processing"],
    "colm": ["large_language_models"],
}


def scrape_ai_deadlines():
    zf = zipfile.ZipFile(io.BytesIO(get(AID_ZIP).content))
    out = []
    for name in zf.namelist():
        if "/src/data/conferences/" not in name or not name.endswith((".yml", ".yaml")):
            continue
        stem = name.rsplit("/", 1)[-1].rsplit(".", 1)[0].lower()
        if stem not in AI_VENUES:
            continue
        try:
            data = yaml.safe_load(zf.read(name)) or []
        except yaml.YAMLError:
            continue
        for c in data:
            start, end = iso(c.get("start")), iso(c.get("end"))
            if not start and c.get("date"):
                start, end = parse_date_range(str(c.get("date")))
            title = f"{c.get('title', '')} {c.get('year', '')}".strip()
            if c.get("full_name"):
                title = f"{title} — {c['full_name']}"
            deadline = None
            for d in c.get("deadlines") or []:
                if d.get("type") in ("paper", "abstract"):
                    dd = iso(str(d.get("date", "")).split(" ")[0])
                    if dd and dd >= today().isoformat():
                        deadline = min(deadline or dd, dd)
            parts = []
            for x in [c.get("venue") or c.get("place"), c.get("city"), c.get("country")]:
                if x and str(x).lower() not in ", ".join(parts).lower():
                    parts.append(str(x))
            loc = ", ".join(parts)
            out.append(ev(title=title, url=c.get("link"), start_date=start,
                          end_date=end or start, deadline=deadline, location=loc or None,
                          country=c.get("country"), source="AI Deadlines",
                          raw_type="conference",
                          declared=list(c.get("tags") or []) + AI_VENUES[stem]))
    return out


# ---------------------------------------------------------------------------
# 2. CADC International Astronomy Meetings
#    The official CADC iCal feed is stale (this is why v1-v4 showed 0 CADC
#    events). We merge (a) the cadc2ical project's cumulative mirror, which is
#    refreshed daily from CADC's live RSS, and (b) CADC's RSS directly.
# ---------------------------------------------------------------------------
CADC_MIRROR = "https://raw.githubusercontent.com/damleborgne/cadc2ical/main/data/meetings.json"
CADC_RSS = [
    "https://www1.cadc-ccda.hia-iha.nrc-cnrc.gc.ca/meetings/rssFeed",
    "https://www.cadc-ccda.hia-iha.nrc-cnrc.gc.ca/meetings/rssFeed",
    "https://cadcwww.dao.nrc.ca/meetings/rssFeed",
]
_CADC_ID = re.compile(r"/meetings/(\d{3,})/?$")


def _cadc_rss(text):
    root = ET.fromstring(text)
    out = {}
    for item in root.iter("item"):
        guid = (item.findtext("guid") or "").strip()
        m = _CADC_ID.search(guid)
        if not m:
            continue
        soup = BeautifulSoup(item.findtext("description") or "", "html.parser")
        rows = {}
        for tr in soup.find_all("tr"):
            cells = tr.find_all(["td", "th"])
            if len(cells) >= 2:
                rows[clean(cells[0].get_text(" ")).lower()] = cells[1]
        start = end = None
        if "date" in rows:
            start, end = parse_date_range(rows["date"].get_text(" "))
        site = None
        for k in ("web site", "website"):
            if k in rows:
                a = rows[k].find("a", href=True)
                site = a["href"] if a else first_url(rows[k].get_text(" "))
        out[m.group(1)] = dict(
            title=clean(item.findtext("title")), start_date=start, end_date=end,
            location=clean(rows["location"].get_text(" ")) if "location" in rows else None,
            website=site, cadc_url=guid)
    return out


def scrape_cadc():
    meetings, got_any = {}, False
    try:
        for m in get(CADC_MIRROR).json().get("meetings", []):
            meetings[m["number"]] = m
        got_any = True
    except Exception as exc:
        print(f"  CADC mirror failed: {exc}")
    for url in CADC_RSS:
        try:
            fresh = _cadc_rss(get(url).text)
        except Exception as exc:
            print(f"  CADC RSS {url} failed: {exc}")
            continue
        for k, m in fresh.items():
            meetings[k] = {**meetings.get(k, {}), **{a: b for a, b in m.items() if b}}
        got_any = True
        break
    if not got_any:
        raise RuntimeError("CADC mirror and all RSS endpoints failed")
    out = []
    for m in meetings.values():
        out.append(ev(title=m.get("title"), url=m.get("website") or m.get("cadc_url"),
                      start_date=m.get("start_date") or None,
                      end_date=m.get("end_date") or m.get("start_date") or None,
                      location=m.get("location") or None,
                      source="CADC Astronomy Meetings", declared=["astrophysics"]))
    return out


# ---------------------------------------------------------------------------
# 3 & 4. INSPIRE-HEP conferences and seminars (JSON API)
#        Rate limit: 15 requests / 5 s per IP. Max page size 1000.
# ---------------------------------------------------------------------------
INSPIRE = "https://inspirehep.net/api"
INSPIRE_PAGES = 4
INSPIRE_SEMINAR_DAYS = 60


def _inspire(kind, fields, max_pages=INSPIRE_PAGES, size=250):
    hits = []
    for page in range(1, max_pages + 1):
        r = get(f"{INSPIRE}/{kind}", params={
            "start_date": "upcoming", "sort": "dateasc", "size": size,
            "page": page, "fields": fields})
        batch = r.json().get("hits", {}).get("hits", [])
        hits.extend(batch)
        if len(batch) < size:
            break
        polite_sleep(0.5)
    return hits


def _inspire_place(addrs):
    if isinstance(addrs, dict):
        addrs = [addrs]
    for a in addrs or []:
        parts = [a.get("place_name")] + list(a.get("cities") or [])
        loc = ", ".join(p for p in parts if p)
        return loc or None, a.get("country_code")
    return None, None


def scrape_inspire_conferences():
    out = []
    fields = ("titles,acronyms,opening_date,closing_date,addresses,urls,"
              "inspire_categories,control_number,short_description,series")
    for h in _inspire("conferences", fields):
        md = h.get("metadata", {})
        titles = md.get("titles") or [{}]
        title = clean(titles[0].get("title"))
        acr = (md.get("acronyms") or [None])[0]
        if acr and acr.lower() not in title.lower():
            title = f"{title} ({acr})"
        loc, cc = _inspire_place(md.get("addresses"))
        urls = md.get("urls") or []
        out.append(ev(
            title=title,
            url=urls[0].get("value") if urls else
            f"https://inspirehep.net/conferences/{md.get('control_number')}",
            start_date=iso(md.get("opening_date")),
            end_date=iso(md.get("closing_date")) or iso(md.get("opening_date")),
            location=loc, country=cc,
            description=clean((md.get("short_description") or {}).get("value")),
            source="INSPIRE conferences", raw_type="conference",
            declared=[c.get("term") for c in md.get("inspire_categories") or []]))
    return out


def scrape_inspire_seminars():
    out = []
    horizon = (today() + dt.timedelta(days=INSPIRE_SEMINAR_DAYS)).isoformat()
    fields = ("title,start_datetime,end_datetime,timezone,speakers,address,urls,"
              "join_urls,inspire_categories,series,abstract,control_number")
    for h in _inspire("seminars", fields, max_pages=3):
        md = h.get("metadata", {})
        start = iso(str(md.get("start_datetime", ""))[:10])
        if start and start > horizon:
            continue
        loc, cc = _inspire_place(md.get("address"))
        speakers = md.get("speakers") or []
        sp = ", ".join(clean(s.get("name")) for s in speakers[:3] if s.get("name"))
        aff = ""
        if speakers and speakers[0].get("affiliations"):
            aff = clean(speakers[0]["affiliations"][0].get("value"))
        series = ", ".join(clean(s.get("name")) for s in md.get("series") or [])
        title = clean((md.get("title") or {}).get("title"))
        out.append(ev(
            title=f"{title} — {sp}" if sp else title,
            url=f"https://inspirehep.net/seminars/{md.get('control_number')}",
            start_date=start, end_date=start, location=loc, country=cc,
            online=bool(md.get("join_urls")) and not loc, tz=md.get("timezone"),
            description=" ".join(x for x in [series, clean((md.get("abstract") or {}).get("value"))] if x),
            speaker=f"{sp} ({aff})" if aff else sp or None,
            source="INSPIRE seminars", raw_type="seminar",
            declared=[c.get("term") for c in md.get("inspire_categories") or []]))
    return out


# ---------------------------------------------------------------------------
# 5. LSST DESC "Cosmology Meetings" public Google Calendar — curated,
#    cosmology-only. Everything here is declared cosmology.
# ---------------------------------------------------------------------------
DESC_ICS = ("https://calendar.google.com/calendar/ical/"
            "a6aumk8bjbhhb9aaa6hg60f19c%40group.calendar.google.com/public/basic.ics")


def scrape_desc_cosmology():
    out = []
    for e in parse_ics(get(DESC_ICS).text):
        title = clean(e.get("SUMMARY"))
        if not title:
            continue
        raw_start = e.get("DTSTART", "")
        start = iso(raw_start)
        all_day = len(raw_start.strip()) == 8
        desc = e.get("DESCRIPTION", "")
        out.append(ev(title=title, url=e.get("URL") or first_url(desc) or
                      "https://lsstdesc.org/CosmologyMeetings/",
                      start_date=start, end_date=ics_end_date(start, e.get("DTEND"), all_day),
                      location=clean(e.get("LOCATION")) or None,
                      description=clean(desc)[:1500],
                      source="DESC Cosmology Meetings", raw_type="conference",
                      declared=["cosmology"]))
    return out


# ---------------------------------------------------------------------------
# 6 & 7. researchseminars.org — talks (8-week window) and conferences
#        GET returns every column, including abstract, topics, room, timezone.
# ---------------------------------------------------------------------------
RS = "https://researchseminars.org/api/0"
RS_WINDOW_DAYS = 56
RS_KEEP = re.compile(r"^(math|physics|astro|gr|hep|quant|cond|nlin|stat|cs_lg|cs_ai|"
                     r"cs_ne|cs_it)", re.I)


def _rs_relevant(topics):
    return any(RS_KEEP.match(re.sub(r"[.\-]", "_", str(t))) for t in topics or [])


def scrape_researchseminars():
    t0 = today()
    q = {"start_time": json.dumps({
        "$gte": t0.isoformat(),
        "$lte": (t0 + dt.timedelta(days=RS_WINDOW_DAYS)).isoformat() + "T23:59:59"})}
    results = get(f"{RS}/search/talks", params=q, timeout=90).json().get("results", [])
    out = []
    for t in results:
        topics = t.get("topics") or []
        if not _rs_relevant(topics):
            continue
        title = clean(t.get("title"))
        if not title or title.upper() in ("TBA", "TBD"):
            continue
        sp = clean(t.get("speaker"))
        aff = clean(t.get("speaker_affiliation"))
        sid, ctr = t.get("seminar_id"), t.get("seminar_ctr")
        start = iso(str(t.get("start_time", ""))[:10])
        room = clean(t.get("room"))
        out.append(ev(
            title=f"{title} — {sp}" if sp else title,
            url=f"https://researchseminars.org/talk/{sid}/{ctr}/" if sid and ctr is not None
            else "https://researchseminars.org/",
            start_date=start, end_date=start,
            location=room or None, online=bool(t.get("online")), tz=t.get("timezone"),
            description=clean(t.get("abstract"))[:2000],
            speaker=f"{sp} ({aff})" if aff else sp or None,
            source="researchseminars.org", raw_type="seminar", declared=topics))
    return out


def scrape_researchseminars_conferences():
    # Since Sep 2026 the API answers HTTP 500 to any date filter on /search/series
    # ({"$gte": ...}); the unfiltered query works (~900 series), so filter here.
    q = {"is_conference": "true", "visibility": "2"}
    results = get(f"{RS}/search/series", params=q, timeout=90).json().get("results", [])
    t = today().isoformat()
    out = []
    for s in results:
        if not _rs_relevant(s.get("topics")):
            continue
        if (iso(s.get("end_date")) or iso(s.get("start_date")) or "") < t:
            continue                                  # past (or undated) conference
        inst = ", ".join(s.get("institutions") or [])
        out.append(ev(
            title=clean(s.get("name")),
            url=s.get("homepage") or f"https://researchseminars.org/seminar/{s.get('shortname')}",
            start_date=iso(s.get("start_date")), end_date=iso(s.get("end_date")),
            location=clean(s.get("room")) or inst or None, online=bool(s.get("online")),
            tz=s.get("timezone"), source="researchseminars.org", raw_type="conference",
            declared=s.get("topics") or []))
    return out
