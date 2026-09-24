"""
Source doctor — run on your own machine (Indian network) to see exactly what
every institute source yields right now:

    python scraper/doctor.py              # every enabled India source
    python scraper/doctor.py --all        # + parked (enabled: false) entries
    python scraper/doctor.py RRI IISc     # only sources whose name contains these words
    python scraper/doctor.py --global     # also the global aggregators

For each source: status, raw items, how many are still upcoming, and the next
three. Paste the output back into the chat when something looks wrong.
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from common import today                            # noqa: E402
from sources_india import india_sources, scrape_watchlist  # noqa: E402


def main(argv):
    flags = {a for a in argv if a.startswith("--")}
    words = [a.lower() for a in argv if not a.startswith("--")]
    registry = india_sources(include_disabled="--all" in flags) + [("Watchlist", scrape_watchlist, 0)]
    if "--global" in flags:
        from scrape import GLOBAL_SOURCES
        registry = GLOBAL_SOURCES + registry
    if words:
        registry = [r for r in registry if any(w in r[0].lower() for w in words)]
    t = today().isoformat()
    print(f"{'status':7} {'raw':>4} {'upcoming':>8}  source")
    print("-" * 78)
    for name, fn, _ in registry:
        t0 = time.time()
        try:
            evs = fn() or []
            up = sorted((e for e in evs if (e.get("end_date") or e.get("start_date") or "") >= t),
                        key=lambda e: e.get("start_date") or "")
            status = "ok" if up else ("past" if evs else "empty")
            print(f"{status:7} {len(evs):4d} {len(up):8d}  {name}  ({time.time() - t0:.1f}s)")
            for e in up[:3]:
                print(f"{'':22}{e.get('start_date')}  {(e.get('title') or '')[:70]}")
        except Exception as exc:
            print(f"{'ERROR':7} {'':4} {'':8}  {name}  -> {exc.__class__.__name__}: {str(exc)[:110]}")
    print("-" * 78)
    print("ok = has upcoming events · past = page works but lists nothing upcoming · "
          "empty = page read, nothing recognised · ERROR = could not fetch")


if __name__ == "__main__":
    main(sys.argv[1:])
