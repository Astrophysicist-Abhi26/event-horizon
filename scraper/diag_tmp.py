"""TEMPORARY probe (removed before merge)."""
import json, requests
H = {"User-Agent": "EventHorizon/5.0 (+https://github.com/Astrophysicist-Abhi26/event-horizon)"}
RS = "https://researchseminars.org/api/0/search/series"
t = "2026-09-24"
for label, q in [
    ("current (end_date $gte)", {"is_conference": "true", "visibility": "2", "end_date": json.dumps({"$gte": t})}),
    ("no date filter", {"is_conference": "true", "visibility": "2"}),
    ("no visibility", {"is_conference": "true", "end_date": json.dumps({"$gte": t})}),
    ("start_date $gte", {"is_conference": "true", "visibility": "2", "start_date": json.dumps({"$gte": t})}),
    ("bool True", {"is_conference": "True"}),
]:
    try:
        r = requests.get(RS, params=q, headers=H, timeout=60)
        body = r.text[:300].replace("\n", " ")
        n = len(r.json().get("results", [])) if r.ok else "-"
        print(f"{label:28} {r.status_code} results={n} :: {body}", flush=True)
    except Exception as e:
        print(f"{label:28} EXC {e.__class__.__name__}: {str(e)[:200]}", flush=True)
for u in ["https://ee.iisc.ac.in/wp-json/tribe/events/v1/events",
          "https://ee.iisc.ac.in/wp-json/tribe/events/v1/events?start_date=2026-09-24&per_page=50&end_date=2027-10-29",
          "https://ee.iisc.ac.in/events/?ical=1"]:
    try:
        r = requests.get(u, headers=H, timeout=30)
        print(f"EE {r.status_code} len={len(r.text)} {u} :: {r.text[:200]!r}", flush=True)
    except Exception as e:
        print("EE EXC", u, e.__class__.__name__, flush=True)
