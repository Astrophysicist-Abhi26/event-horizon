"""TEMPORARY network diagnostics, run in GitHub Actions (removed before merge)."""
import os, re, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bs4 import BeautifulSoup
from common import HTTP, _BROWSER_HEADERS, clean
from listing import extract_listing
import sources_india as SI

PAGES = sys.argv[1:] or []

def fetch(url, browser=False, verify=True):
    try:
        r = HTTP.get(url, timeout=30, verify=verify, headers=_BROWSER_HEADERS if browser else {})
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

if __name__ == "__main__":
    for u in [
        "https://www.iiap.res.in/",
        "https://www.iiap.res.in/upcoming_colloquium.php",
        "https://events.iiap.res.in/",
        "https://events.iiap.res.in/export/categ/0.json?from=today&to=+400d",
        "https://events.iiap.res.in/indico/",
        "https://physics.iisc.ac.in/events-all/conferences/",
        "https://physics.iisc.ac.in/events-all/schools/",
        "https://physics.iisc.ac.in/events-all/",
        "https://ee.iisc.ac.in/wp-json/tribe/events/v1/events",
        "https://ee.iisc.ac.in/events/?ical=1",
        "https://ee.iisc.ac.in/",
        "https://www.csa.iisc.ac.in/wp-json/tribe/events/v1/events",
        "https://www.csa.iisc.ac.in/events/?ical=1",
        "https://www.csa.iisc.ac.in/",
        "https://www.imsc.res.in/",
        "https://www.tifr.res.in/~daa/events.html",
        "https://www.tifr.res.in/~daa/",
        "https://indico.tifr.res.in/",
        "https://indico.tifr.res.in/indico/",
        "https://conf1.ncra.tifr.res.in/",
        "https://conf1.ncra.tifr.res.in/export/categ/0.json?from=today&to=+400d",
        "https://www.iucaa.in/en/other-info/9-upcoming-events-at-iucaa",
        "https://www.iucaa.in/en/iucaa-events/events-outside-iucaa",
        "https://www.astron-soc.in/announcement",
        "https://www.rri.res.in/meetings",
        "https://www.jncasr.ac.in/research/research-units/theoretical-sciences-unit/events",
        "https://researchseminars.org/api/0/search/series?is_conference=true&visibility=2",
    ]:
        show(u)
    show("https://www.imsc.res.in/", browser=True)
    for n in ["RRI meetings", "RRI talks", "JNCASR Theoretical Sciences Unit", "JNCASR events",
              "IUCAA (events outside IUCAA)", "IISc Mathematics seminars", "IISc (institute events)",
              "IISc Physics (department calendars)"]:
        listing(n)
