"""
Generic extractor for institute "upcoming events" pages.

Rule that fixes the v1-v4 ICTS bug (menu links scraped as events):
an item is kept ONLY if its link and a parseable date live in the same small
page block. Navigation, headers, footers, scripts and forms are removed first,
and a block that contains several event links is treated as a list container
(too big to date a single item), so its date is never borrowed.
"""

import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from common import clean, get, parse_date_range

NAV_WORDS = re.compile(
    r"^(home|about|contact|programs?|past programs?|current (?:&|and) upcoming|"
    r"upcoming|lectures?|events?|special (?:events|lectures)|summer courses?|"
    r"program committee|people|news|read more|more|details|register|"
    r"registration|apply|click here|here|load more|view all.*|archives?)$", re.I)
MAX_BLOCK_CHARS = 900
MAX_CLIMB = 5


# Class tokens that mark page chrome. Matched against WHOLE tokens: v5 matched
# any class containing "-header", which deleted Drupal "views-accordion-header"
# (ASI: every title) and "card-header"/"event-header" blocks on other sites.
_CHROME_CLASS = re.compile(
    r"^(?:site-|main-|page-|global-|top-|primary-|mobile-)?"
    r"(?:nav|navbar|navigation|menu|menubar|mainmenu|breadcrumbs?|footer|header|masthead)$", re.I)
# "Posted on 18 Sep" stamps are publication dates, not event dates.
_POSTED_CLASS = re.compile(r"(?:^|[-_])(?:created|posted|submitted|post-date|entry-date|"
                           r"published|last-updated|updated-date)(?:$|[-_])", re.I)
# Link texts that say nothing about the event: the title is then taken from the
# block's heading (IISc Physics: <h2>ICMS 2026</h2> ... <a>Website</a>).
GENERIC_LINK = re.compile(r"^(?:website|web ?page|more info(?:rmation)?|read more|details|"
                          r"know more|click here|here|link|visit|view|more)\W*$", re.I)
# Announcement-board items that are not events in their own right.
_NOT_EVENT = re.compile(r"^https?://|\bdeadline\b.*\b(extended|is)\b|\bextended (till|upto|up to|until)\b|"
                        r"^(registration|abstract|proposal)s?\b.*\bdeadline\b|proposal submission", re.I)
_CHROME_MAX_SHARE = 0.4      # never strip a wrapper holding this much of the page's text


def _strip_chrome(soup):
    for tag in soup.find_all(["script", "style", "noscript", "form"]):
        tag.decompose()
    root = soup.body or soup
    total = max(1, len(root.get_text(" ", strip=True)))

    def small(tag):
        return len(tag.get_text(" ", strip=True)) < _CHROME_MAX_SHARE * total

    cands = soup.find_all(["nav", "header", "footer", "aside"])
    cands += soup.find_all(attrs={"role": re.compile("navigation|banner|contentinfo")})
    cands += soup.find_all(class_=lambda c: bool(c) and bool(_CHROME_CLASS.match(c)))
    for tag in cands:
        if not tag.decomposed and small(tag):
            tag.decompose()
    for tag in soup.find_all(class_=lambda c: bool(c) and bool(_POSTED_CLASS.search(c))):
        if not tag.decomposed:
            tag.decompose()


def _same_site(href, base_host):
    host = urlparse(href).netloc.lower()
    return not host or host.endswith(base_host) or base_host.endswith(host)


def _link_text(a):
    """Visible text, else the title/alt of an image link (IUCAA: poster links)."""
    t = clean(a.get_text(" "))
    if t:
        return t
    img = a.find("img")
    return clean(a.get("title") or (img and (img.get("alt") or img.get("title"))) or "")


def _heading(node, min_title):
    min_title = min(min_title, 6)            # "ICMS 2026" is a fine heading
    for h in node.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "strong", "b"]):
        t = clean(h.get_text(" "))
        if len(t) >= min_title and not NAV_WORDS.match(t) and not parse_date_range(t)[0] \
                and not t.rstrip(":").lower() in ("date", "venue", "time", "speaker"):
            return t
    return None


def extract_listing(url, source, default_location, href_filter=None,
                    min_title=10, raw_type=None, html=None, insecure_ok=False):
    soup = BeautifulSoup(html if html is not None else get(url, insecure_ok=insecure_ok).text,
                         "html.parser")
    base_host = urlparse(url).netloc.lower().removeprefix("www.")
    _strip_chrome(soup)
    hf = re.compile(href_filter, re.I) if href_filter else None

    def eventish(x):
        """Could this link itself be an event? (for list-container detection)"""
        t = _link_text(x)
        if GENERIC_LINK.match(t):
            return True
        return ((not hf or hf.search(x["href"])) and _same_site(x["href"], base_host)
                and len(t) >= min_title and not NAV_WORDS.match(t))

    out, seen = [], set()
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if href.startswith(("#", "mailto:", "javascript:")):
            continue
        if hf and not hf.search(href):
            continue
        title = _link_text(a)
        generic = bool(GENERIC_LINK.match(title))
        if not generic and (len(title) < min_title or NAV_WORDS.match(title)):
            continue
        node, start, end, desc = a, None, None, ""
        for _ in range(MAX_CLIMB):
            node = node.parent
            if node is None or node.name in ("body", "html", "[document]"):
                break
            text = clean(node.get_text(" "))
            if len(text) > MAX_BLOCK_CHARS:
                break
            # Only links that could themselves be events count towards "this is a
            # list container": a YouTube / Zoom / registration link sitting in
            # the same row as the event (RRI talks do this) must not hide it.
            links = [x for x in node.find_all("a", href=True) if eventish(x)]
            if len({urljoin(url, x["href"]) for x in links}) > 1:
                break  # reached a list container
            if generic:
                h = _heading(node, min_title)
                if not h:
                    continue
                title = h
            start, end = parse_date_range(text)
            if start:
                desc = text.replace(title, " ").strip()[:500]
                break
        if not start or (generic and GENERIC_LINK.match(title)) or _NOT_EVENT.search(title):
            continue  # undated (or untitled) -> not an event we can place in time
        full = urljoin(url, href)
        key = (title.lower(), start)
        if key in seen:
            continue
        seen.add(key)
        out.append(dict(title=title, url=full, start_date=start, end_date=end or start,
                        deadline=None, location=default_location, country=None,
                        online=False, tz=None, description=desc, speaker=None,
                        source=source, raw_type=raw_type, declared=[], priority=False))
    return out
