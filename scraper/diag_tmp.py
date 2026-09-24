"""TEMPORARY network diagnostics, run in GitHub Actions (removed before merge)."""
import os, re, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bs4 import BeautifulSoup
from common import HTTP, _BROWSER_HEADERS, clean
from listing import extract_listing
import sources_india as SI

PAGES = sys.argv[1:] or []

import requests
from concurrent.futures import ThreadPoolExecutor
import io, contextlib
import urllib3
urllib3.disable_warnings()

def fetch(url, browser=False, verify=True):
    try:
        r = requests.get(url, timeout=(6, 15), verify=verify,
                         headers=_BROWSER_HEADERS if browser else {"User-Agent": HTTP.headers["User-Agent"]})
        return r
    except Exception as e:
        print(f"   !! {e.__class__.__name__}: {str(e)[:200]}")
        return None

def show(url, anchors=True, browser=False, verify=True, n_text=900, n_links=150):
    print("\n" + "=" * 100 + f"\n### {url}  (browser={browser} verify={verify})")
    r = fetch(url, browser, verify)
    if r is None and verify:
        r = fetch(url, browser, False)
    if r is None:
        return
    print(f"   status={r.status_code} final={r.url} type={r.headers.get('content-type')} len={len(r.text)}")
    ct = r.headers.get("content-type", "")
    if "json" in ct or r.text.lstrip()[:1] in "[{":
        print("   JSON head:", r.text[:1500].replace("\n", " "))
        return
    if "calendar" in ct or r.text.startswith("BEGIN:VCALENDAR"):
        print("   ICS head:", r.text[:800])
        return
    soup = BeautifulSoup(r.text, "html.parser")
    print("   title:", clean(soup.title.get_text()) if soup.title else None)
    for t in soup(["script", "style", "noscript"]):
        t.decompose()
    print("   TEXT:", clean(soup.get_text(" "))[:n_text])
    if anchors:
        seen = set()
        k = 0
        for a in soup.find_all("a", href=True):
            txt = clean(a.get_text(" "))[:90]
            h = a["href"].strip()
            if (txt, h) in seen or len(txt) < 3 or h.startswith(("#", "mailto:", "javascript:")):
                continue
            seen.add((txt, h))
            print(f"   A: {txt} -> {h}")
            k += 1
            if k >= n_links:
                break

def listing(name):
    cfg = next(e for e in SI._registry(True) if e["name"] == name)
    print("\n" + "#" * 100 + f"\n## LISTING ITEMS for {name}")
    try:
        evs = SI.ADAPTERS[cfg.get("kind", "listing")](cfg)
        for e in evs[:40]:
            print(f"   {e['start_date']}..{e['end_date']} | {e['title'][:80]} | {e['url'][:90]}")
    except Exception as e:
        print("   !!", e.__class__.__name__, str(e)[:300])

def captured(fn, *a, **k):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        try:
            fn(*a, **k)
        except Exception as e:
            print("   !! crashed", e)
    return buf.getvalue()

from listing import _strip_chrome

def body(url, insecure=False, n=2500, nl=60):
    print("\n" + "=" * 100 + f"\n### BODY {url}")
    r = fetch(url, verify=not insecure)
    if r is None:
        return
    print(f"   status={r.status_code} len={len(r.text)}")
    soup = BeautifulSoup(r.text, "html.parser")
    for t in soup(["script", "style", "noscript"]):
        t.decompose()
    _strip_chrome(soup)
    main = soup.find("main") or soup.find(id=re.compile("content|main", re.I)) or soup.body or soup
    print("   BODY:", clean(main.get_text(" "))[:n])
    k = 0
    for a in main.find_all("a", href=True):
        txt = clean(a.get_text(" "))[:90]
        if len(txt) >= 6:
            print(f"   A: {txt} -> {a['href'][:120]}")
            k += 1
            if k >= nl:
                break

import base64, gzip

if __name__ == "__main__":
    for name, u in [
        ("iisc_phys_conf", "https://physics.iisc.ac.in/events-all/conferences/"),
        ("iisc_phys_schools", "https://physics.iisc.ac.in/events-all/schools/"),
        ("iucaa_upcoming", "https://www.iucaa.in/en/other-info/9-upcoming-events-at-iucaa"),
        ("asi_announce", "https://www.astron-soc.in/announcement"),
        ("ee_eventdir", "https://ee.iisc.ac.in/event-directory/"),
        ("csa_home", "https://www.csa.iisc.ac.in/"),
        ("tifr_daa_list", "https://www.tifr.res.in/~daa/events_list.html"),
        ("tifr_daa_sched", "https://www.tifr.res.in/~daa/events_scheduled.html"),
        ("iia_cat6", "https://events.iiap.res.in/category/6/events.ics"),
    ]:
        r = fetch(u, verify=not u.startswith("https://events.iiap"))
        if r is None:
            print("HTMLB64", name, "FAILED"); continue
        b = base64.b64encode(gzip.compress(r.content, 9)).decode()
        print("HTMLB64", name, r.status_code, b, flush=True)
