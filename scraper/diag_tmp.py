"""TEMPORARY probe (removed before merge)."""
import os, sys, base64, gzip, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import requests
from common import UA, _BROWSER_HEADERS
from listing import extract_listing
for u in ["https://www.astron-soc.in/announcement", "https://physics.iisc.ac.in/events-all/conferences/",
          "https://physics.iisc.ac.in/events-all/schools/", "https://physics.iisc.ac.in/"]:
    for name, h in [("botUA", {"User-Agent": UA}), ("browser", _BROWSER_HEADERS)]:
        for attempt in range(2):
            try:
                r = requests.get(u, headers=h, timeout=30)
                print(f"{name:7} try{attempt} {r.status_code} len={len(r.text)} final={r.url} server={r.headers.get('server')} :: {r.text[:160]!r}", flush=True)
                if r.ok and "astron-soc" in u:
                    evs = extract_listing(u, "ASI", "India", html=r.text)
                    print("   ASI items:", len(evs), [e["title"][:50] for e in evs[:4]], flush=True)
                    if not evs:
                        print("HTMLB64 asi_now", base64.b64encode(gzip.compress(r.content, 9)).decode(), flush=True)
            except Exception as e:
                print(f"{name:7} try{attempt} EXC {e.__class__.__name__}: {str(e)[:150]}", flush=True)
            time.sleep(3)
