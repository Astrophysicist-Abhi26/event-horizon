"""TEMPORARY probe (removed before merge)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sources as G
evs = G.scrape_researchseminars_conferences()
print("researchseminars.org conferences:", len(evs), "upcoming & relevant", flush=True)
for e in sorted(evs, key=lambda e: e["start_date"] or "")[:12]:
    print("  ", e["start_date"], e["end_date"], "|", (e["title"] or "")[:80])
