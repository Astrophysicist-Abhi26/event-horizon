"""
Shared helpers for every Event Horizon source.

One HTTP session with retries, one date parser that understands the date
formats academic sites actually use, and a tolerant iCal reader.
"""

import datetime as dt
import html as _html
import re
import time

import requests
from dateutil import parser as dateparser
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

UA = ("EventHorizon/5.0 (personal academic event aggregator; "
      "+https://github.com/Astrophysicist-Abhi26/event-horizon)")
TIMEOUT = 30


def session():
    s = requests.Session()
    retry = Retry(total=3, backoff_factor=1.5,
                  status_forcelist=(429, 500, 502, 503, 504),
                  allowed_methods=("GET",), respect_retry_after_header=True)
    s.mount("https://", HTTPAdapter(max_retries=retry))
    s.mount("http://", HTTPAdapter(max_retries=retry))
    s.headers.update({"User-Agent": UA})
    return s


HTTP = session()


BROWSER_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")
_BROWSER_HEADERS = {"User-Agent": BROWSER_UA,
                    "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
                    "Accept-Language": "en-IN,en;q=0.9"}


def get(url, insecure_ok=False, **kw):
    """GET with retries. Two fallbacks, both needed by Indian institute sites:
    * 403/406 with our honest bot UA -> retry once with a browser UA
      (several .res.in / .ac.in firewalls reject unknown agents outright);
    * TLS certificate-chain error -> retry without verification, but ONLY
      for sources marked `insecure_ok: true` in institutes.yaml (read-only
      public pages whose servers ship an incomplete certificate chain).
    """
    kw.setdefault("timeout", TIMEOUT)
    headers = kw.pop("headers", None) or {}
    verify = True
    try:
        r = HTTP.get(url, headers=headers, **kw)
    except requests.exceptions.SSLError:
        if not insecure_ok:
            raise
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        verify = False
        r = HTTP.get(url, headers=headers, verify=False, **kw)
    if r.status_code in (403, 406):
        r = HTTP.get(url, headers={**headers, **_BROWSER_HEADERS}, verify=verify, **kw)
    r.raise_for_status()
    return r


def polite_sleep(seconds=0.4):
    time.sleep(seconds)


def today():
    return dt.date.today()


# ---------------------------------------------------------------------------
# Text
# ---------------------------------------------------------------------------
def clean(text):
    if text is None:
        return ""
    text = _html.unescape(str(text))
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def norm_title(title):
    """Canonical form used for cross-source de-duplication."""
    t = clean(title).lower()
    t = re.sub(r"\b(20\d\d)\b", r" \1 ", t)
    t = re.sub(r"[^a-z0-9 ]+", " ", t)
    t = re.sub(r"\b(the|a|an|on|of|and|in|for|at|workshop|conference|"
               r"international|meeting|school)\b", " ", t)
    return re.sub(r"\s+", " ", t).strip()


# ---------------------------------------------------------------------------
# Dates
# ---------------------------------------------------------------------------
MONTHS = ("jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec|january|"
          "february|march|april|june|july|august|september|october|"
          "november|december")
_M = rf"(?:{MONTHS})\.?"
_SEP = r"\s*(?:-|–|—|to|until|till)\s*"
_WD = r"(?:(?:mon|tue|wed|thu|fri|sat|sun)[a-z]*,?\s+)?"   # optional weekday

# Ordered from most to least specific. Each yields (start_text, end_text).
_RANGE_PATTERNS = [
    # 06 July 2026 to 10 July 2026 / 30 Nov 2026 - 4 Dec 2026
    re.compile(rf"(\d{{1,2}},?\s+{_M},?\s+\d{{4}}){_SEP}{_WD}(\d{{1,2}},?\s+{_M},?\s+\d{{4}})", re.I),
    # November 30, 2025 - December 7, 2025
    re.compile(rf"({_M}\s+\d{{1,2}},?\s+\d{{4}}){_SEP}({_M}\s+\d{{1,2}},?\s+\d{{4}})", re.I),
    # 30 Nov - 4 Dec 2026 / 30 Nov - 4 Dec, 2026
    re.compile(rf"(\d{{1,2}}\s+{_M}){_SEP}(\d{{1,2}}\s+{_M},?\s+(\d{{4}}))", re.I),
    # November 30 - December 7, 2025
    re.compile(rf"({_M}\s+\d{{1,2}}){_SEP}({_M}\s+\d{{1,2}},?\s+(\d{{4}}))", re.I),
    # 7-11 September 2026 / 7 – 11 Sep 2026 / 13 – 17 December, 2025
    re.compile(rf"(\d{{1,2}}){_SEP}(\d{{1,2}})\s+({_M}),?\s+(\d{{4}})", re.I),
    # September 7-11, 2026
    re.compile(rf"({_M})\s+(\d{{1,2}}){_SEP}(\d{{1,2}}),?\s+(\d{{4}})", re.I),
    # ISO range 2026-09-07 to 2026-09-11
    re.compile(rf"(\d{{4}}-\d{{2}}-\d{{2}}){_SEP}(\d{{4}}-\d{{2}}-\d{{2}})"),
    # Indian numeric, day first: 01/02/2027 - 05/02/2027 (also "01/02/2027 05/02/2027"
    # when a table puts start and end in adjacent cells)
    re.compile(r"\b(\d{1,2}[/.]\d{1,2}[/.]\d{4})(?:\s*(?:-|–|—|to|until|till)\s*|\s+)"
               r"(\d{1,2}[/.]\d{1,2}[/.]\d{4})\b"),
]
_SINGLE_PATTERNS = [
    re.compile(r"(\d{4}-\d{2}-\d{2})"),
    re.compile(r"\b(\d{1,2}[/.]\d{1,2}[/.]\d{4})\b"),
    re.compile(rf"(\d{{1,2}}(?:st|nd|rd|th)?,?\s+{_M},?\s+\d{{4}})", re.I),
    re.compile(rf"({_M}\s+\d{{1,2}}(?:st|nd|rd|th)?,?\s+\d{{4}})", re.I),
]


def iso(value, dayfirst=True):
    """Best-effort 'YYYY-MM-DD' or None. Never invents a year."""
    if value is None or value == "":
        return None
    if isinstance(value, dt.datetime):
        return value.date().isoformat()
    if isinstance(value, dt.date):
        return value.isoformat()
    if isinstance(value, dict):  # Indico {"date": ..., "time": ...}
        value = value.get("date") or ""
    s = clean(value)
    m = re.match(r"^(\d{4})(\d{2})(\d{2})(?:T|$)", s)  # iCal 20261012 / 20261012T...
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    if not re.search(r"\d{4}", s):
        return None
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})", s)            # ISO: never reinterpret
    if m:
        try:
            return dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3))).isoformat()
        except ValueError:
            return None
    s = re.sub(r"(\d)(st|nd|rd|th)\b", r"\1", s)
    # Parse twice with different defaults: if the results differ, the text was
    # missing a day or month and dateutil silently filled it in -> reject.
    try:
        a = dateparser.parse(s, fuzzy=True, dayfirst=dayfirst,
                             default=dt.datetime(2000, 1, 1))
        b = dateparser.parse(s, fuzzy=True, dayfirst=dayfirst,
                             default=dt.datetime(2001, 2, 2))
    except (ValueError, OverflowError, TypeError):
        return None
    if (a.month, a.day) != (b.month, b.day) or a.year != b.year:
        return None
    return a.date().isoformat()


def _dmy(s):
    """'01/02/2027' -> '2027-02-01' (Indian convention: day first). Rejects
    impossible dates instead of guessing."""
    m = re.fullmatch(r"(\d{1,2})[/.](\d{1,2})[/.](\d{4})", s.strip())
    if not m:
        return None
    try:
        return dt.date(int(m.group(3)), int(m.group(2)), int(m.group(1))).isoformat()
    except ValueError:
        return None


def parse_date_range(text):
    """Find the first date or date range in free text -> (start, end)."""
    if not text:
        return None, None
    t = clean(text).replace("\u2009", " ")
    for i, pat in enumerate(_RANGE_PATTERNS):
        m = pat.search(t)
        if not m:
            continue
        g = m.groups()
        if i in (0, 1, 6):
            a, b = iso(g[0]), iso(g[1])
        elif i == 7:
            a, b = _dmy(g[0]), _dmy(g[1])
        elif i in (2, 3):
            a, b = iso(f"{g[0]} {g[2]}"), iso(g[1])
        elif i == 4:
            a, b = iso(f"{g[0]} {g[2]} {g[3]}"), iso(f"{g[1]} {g[2]} {g[3]}")
        else:
            a, b = iso(f"{g[1]} {g[0]} {g[3]}"), iso(f"{g[2]} {g[0]} {g[3]}")
        if a and b and b < a:  # "Dec 28 - Jan 3, 2027": start is previous year
            try:
                a = (dt.date.fromisoformat(a).replace(year=int(b[:4]) - 1)).isoformat()
            except ValueError:
                pass
        if a:
            return a, b or a
    for pat in _SINGLE_PATTERNS:
        m = pat.search(t)
        if m:
            d = _dmy(m.group(1)) if re.fullmatch(r"\d{1,2}[/.]\d{1,2}[/.]\d{4}", m.group(1)) \
                else iso(m.group(1))
            if d:
                return d, d
    return None, None


# ---------------------------------------------------------------------------
# iCal (RFC 5545) — small tolerant reader, enough for public calendars
# ---------------------------------------------------------------------------
def parse_ics(text):
    lines = []
    for raw in text.splitlines():
        if raw[:1] in (" ", "\t") and lines:
            lines[-1] += raw[1:]
        else:
            lines.append(raw.rstrip("\r"))
    events, ev = [], None
    for ln in lines:
        if ln == "BEGIN:VEVENT":
            ev = {}
        elif ln == "END:VEVENT" and ev is not None:
            events.append(ev)
            ev = None
        elif ev is not None and ":" in ln:
            key, val = ln.split(":", 1)
            key = key.split(";")[0].upper()
            val = (val.replace("\\,", ",").replace("\\;", ";")
                      .replace("\\n", "\n").replace("\\N", "\n").strip())
            ev[key] = val
    return events


def ics_end_date(start, dtend_raw, all_day):
    """iCal all-day DTEND is exclusive; convert to inclusive end."""
    end = iso(dtend_raw) if dtend_raw else None
    if end and all_day and start and end > start:
        end = (dt.date.fromisoformat(end) - dt.timedelta(days=1)).isoformat()
    return end or start


def first_url(text):
    m = re.search(r"https?://[^\s<>\"')]+", text or "")
    return m.group(0).rstrip(".,;") if m else None
