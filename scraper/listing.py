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


def _strip_chrome(soup):
    for tag in soup.find_all(["nav", "header", "footer", "script", "style",
                              "noscript", "form", "aside"]):
        tag.decompose()
    for tag in soup.find_all(attrs={"role": re.compile("navigation|banner|contentinfo")}):
        tag.decompose()
    for tag in soup.find_all(class_=re.compile(r"(^|[-_ ])(nav|menu|breadcrumb|footer|header)", re.I)):
        tag.decompose()


def _same_site(href, base_host):
    host = urlparse(href).netloc.lower()
    return not host or host.endswith(base_host) or base_host.endswith(host)


def extract_listing(url, source, default_location, href_filter=None,
                    min_title=10, raw_type=None, html=None, insecure_ok=False):
    soup = BeautifulSoup(html if html is not None else get(url, insecure_ok=insecure_ok).text,
                         "html.parser")
    base_host = urlparse(url).netloc.lower().removeprefix("www.")
    _strip_chrome(soup)
    hf = re.compile(href_filter, re.I) if href_filter else None
    out, seen = [], set()
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if href.startswith(("#", "mailto:", "javascript:")):
            continue
        if hf and not hf.search(href):
            continue
        title = clean(a.get_text(" "))
        if len(title) < min_title or NAV_WORDS.match(title):
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
            links = [x for x in node.find_all("a", href=True)
                     if (not hf or hf.search(x["href"])) and _same_site(x["href"], base_host)
                     and len(clean(x.get_text(" "))) >= min_title
                     and not NAV_WORDS.match(clean(x.get_text(" ")))]
            if len({urljoin(url, x["href"]) for x in links}) > 1:
                break  # reached a list container
            start, end = parse_date_range(text)
            if start:
                desc = text.replace(title, " ").strip()[:500]
                break
        if not start:
            continue  # undated -> not an event we can place in time
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
