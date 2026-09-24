"""
Event Horizon v5 — daily pipeline.

  sources -> health check -> normalise -> drop past/undated -> de-duplicate
  -> classify (declared codes + keywords + embeddings [+ Claude]) -> score
  -> docs/events.json  (+ notification files for the GitHub Action)

Run locally:  python scraper/scrape.py
Options (env): EH_DIGEST=1 forces the weekly digest; ANTHROPIC_API_KEY enables
Option C; EH_NO_EMBED=1 skips Option B (faster local runs).
"""

import datetime as dt
import hashlib
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import taxonomy as T                                      # noqa: E402
from classify import classify                             # noqa: E402
from common import clean, norm_title, today               # noqa: E402
from geo import locate                                     # noqa: E402
import sources as G                                        # noqa: E402
from sources_india import india_sources, scrape_issue_intake, scrape_watchlist  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EVENTS = os.path.join(ROOT, "docs", "events.json")
NOTIFY_DIR = os.path.join(ROOT, "notify")
HORIZON_DAYS = 730

GLOBAL_SOURCES = [
    # (name, function, minimum events expected when healthy)
    ("DESC Cosmology Meetings", G.scrape_desc_cosmology, 5),
    ("CADC Astronomy Meetings", G.scrape_cadc, 30),
    ("INSPIRE conferences", G.scrape_inspire_conferences, 50),
    ("INSPIRE seminars", G.scrape_inspire_seminars, 10),
    ("researchseminars.org talks", G.scrape_researchseminars, 30),
    ("researchseminars.org conferences", G.scrape_researchseminars_conferences, 1),
    ("AI Deadlines", G.scrape_ai_deadlines, 3),
]

# Earlier source = preferred copy when the same event appears twice
SOURCE_PRIORITY = ["Added by you", "Watchlist", "DESC Cosmology Meetings"]
MANUAL = {"Watchlist", "Added by you"}

TYPE_RULES = [
    (r"\bschools?\b", "School"), (r"summer course|winter course|refresher course", "School"),
    (r"lecture series|lectures\b|distinguished lecture|memorial lecture", "Lecture series"),
    (r"\bworkshops?\b|hackathon|discussion meeting|\bprogram(me)?\b|thinkshop|hands-on", "Workshop"),
    (r"conference|symposium|congress|meeting|\bforum\b|\bdays\b|summit|\bfest\b", "Conference"),
    (r"colloqui|seminar|\btalks?\b|webinar|journal club|lecture\b", "Talk / Seminar"),
]
NOT_EVENTS = re.compile(
    r"^(programs?|past programs?|program committee|lectures?|events?|current (&|and) upcoming|"
    r"special (events|lectures)|summer courses?|archives?|home|news|load more)$", re.I)


def classify_type(title, raw_type, source):
    text = f"{raw_type or ''} {title or ''}".lower()
    for pat, label in TYPE_RULES:
        if re.search(pat, text):
            return label
    if raw_type and "seminar" in raw_type.lower():
        return "Talk / Seminar"
    return "Talk / Seminar" if "seminar" in (source or "").lower() else "Conference"


def event_id(title, start):
    return hashlib.sha1(f"{norm_title(title)}|{start or ''}".encode()).hexdigest()[:12]


def load_previous():
    try:
        with open(EVENTS) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


# ---------------------------------------------------------------------------
def run_sources(prev_health):
    registry = GLOBAL_SOURCES + india_sources() + [("Watchlist", scrape_watchlist, 0),
                                                  ("Added by you", scrape_issue_intake, 0)]
    raw, health = [], []
    prev = {h["name"]: h for h in prev_health or []}
    for name, fn, min_exp in registry:
        t0 = time.time()
        try:
            batch = fn() or []
            status = "ok" if len(batch) >= max(1, min_exp) else ("low" if batch else "empty")
            if name in MANUAL and not batch:
                status = "ok"
            msg = ""
        except Exception as exc:
            batch, status, msg = [], "error", f"{exc.__class__.__name__}: {exc}"[:300]
        secs = round(time.time() - t0, 1)
        last_ok = dt.datetime.now(dt.timezone.utc).isoformat() if status == "ok" \
            else prev.get(name, {}).get("last_ok")
        health.append(dict(name=name, status=status, raw=len(batch), kept=0,
                           message=msg, seconds=secs, last_ok=last_ok,
                           previous=prev.get(name, {}).get("status")))
        print(f"[{status:5s}] {name}: {len(batch)} raw ({secs}s) {msg}")
        for e in batch:
            e["source"] = name
        raw.extend(batch)
    return raw, health


def normalise(raw):
    t = today().isoformat()
    horizon = (today() + dt.timedelta(days=HORIZON_DAYS)).isoformat()
    out = []
    for e in raw:
        title = clean(e.get("title"))
        if not title or not e.get("url") or NOT_EVENTS.match(title):
            continue
        start = e.get("start_date")
        end = e.get("end_date") or start
        if start and end and end < start:
            end = start
        if not start and not e.get("priority"):
            continue                       # undated: cannot be placed in time
        if (end or start or t) < t:
            continue                       # already over
        if start and start > horizon:
            continue
        country, region, online = locate(e.get("location"), e.get("country"),
                                         e.get("online"), e.get("tz"))
        out.append(dict(
            id=event_id(title, start), title=title, url=e["url"], start_date=start,
            end_date=end, deadline=e.get("deadline"), location=clean(e.get("location")) or None,
            country=country, region=region, online=online,
            type=classify_type(title, e.get("raw_type"), e.get("source")),
            source=e.get("source"), sources=[e.get("source")],
            speaker=e.get("speaker"), description=clean(e.get("description")),
            declared=[d for d in (e.get("declared") or []) if d],
            priority=bool(e.get("priority"))))
    return out


def _rank(e):
    s = e["source"]
    return (SOURCE_PRIORITY.index(s) if s in SOURCE_PRIORITY else len(SOURCE_PRIORITY),
            -len(e["description"] or ""), -len(e["declared"]))


def dedupe(events):
    """Same normalised title + same start date = same event. Also merges when
    one normalised title contains the other on the same start date."""
    by_date = {}
    for e in events:
        by_date.setdefault(e["start_date"], []).append(e)
    out = []
    for date, group in by_date.items():
        group.sort(key=_rank)
        kept = []
        for e in group:
            nt = norm_title(e["title"])
            ns = set(nt.split())
            twin = None
            for k in kept:
                kt = norm_title(k["title"])
                ks = set(kt.split())
                jac = len(ns & ks) / max(1, len(ns | ks))
                if nt == kt or (min(len(nt), len(kt)) >= 14 and (nt in kt or kt in nt)) \
                        or (min(len(ns), len(ks)) >= 3 and jac >= 0.8):
                    twin = k
                    break
            if twin is None:
                kept.append(e)
                continue
            for s in e["sources"]:
                if s not in twin["sources"]:
                    twin["sources"].append(s)
            twin["declared"] = sorted(set(twin["declared"]) | set(e["declared"]))
            twin["priority"] = twin["priority"] or e["priority"]
            for f in ("deadline", "location", "speaker", "end_date"):
                twin[f] = twin[f] or e[f]
            if len(e["description"] or "") > len(twin["description"] or ""):
                twin["description"] = e["description"]
            if twin["region"] == "unknown" and e["region"] != "unknown":
                twin.update(country=e["country"], region=e["region"])
        out.extend(kept)
    return out


def classify_all(events):
    status = {}
    embed_results = [None] * len(events)
    if os.environ.get("EH_NO_EMBED"):
        status["embedding"] = {"status": "off", "detail": "disabled by EH_NO_EMBED"}
    else:
        try:
            from embed import EmbeddingClassifier
            clf = EmbeddingClassifier()
            embed_results = clf.classify_many(events)
            status["embedding"] = {"status": clf.status, "detail": clf.detail}
        except Exception as exc:
            status["embedding"] = {"status": "off", "detail": f"{exc}"[:200]}
    try:
        from llm_classify import classify_all as llm_all
        llm_results, status["llm"] = llm_all(events)
    except Exception as exc:
        llm_results, status["llm"] = [None] * len(events), {"status": "off", "detail": f"{exc}"[:200]}
    for e, emb, llm in zip(events, embed_results, llm_results):
        subs, fields, score, basis = classify(e, emb if emb and emb[0] != "neg" else None, llm)
        e.update(subfields=subs, fields=fields, score=score, basis=basis)
        if llm and llm.get("reason"):
            e["reason"] = llm["reason"]
        if e["priority"]:
            e["score"] = max(e["score"], 60)
    return status


# ---------------------------------------------------------------------------
def notifications(events, prev_ids, health):
    os.makedirs(NOTIFY_DIR, exist_ok=True)
    for f in os.listdir(NOTIFY_DIR):
        os.remove(os.path.join(NOTIFY_DIR, f))
    t = today().isoformat()

    def line(e):
        where = e["location"] or e["region"]
        when = e["start_date"] or "date TBA"
        dl = f" · **deadline {e['deadline']}**" if e.get("deadline") else ""
        sf = ", ".join(T.SUBFIELDS[s][1] for s in e["subfields"][:2])
        return (f"- **[{e['title']}]({e['url']})** — {e['type']}, {where}, {when}{dl}  \n"
                f"  _{sf or 'unclassified'} · relevance {e['score']}_")

    # urgent: brand-new AND (very relevant, or local and relevant, or pinned)
    if prev_ids:
        urgent = [e for e in events if e["id"] not in prev_ids and (
            e["priority"] or e["score"] >= T.URGENT_MIN_SCORE or
            (e["region"] == "bengaluru" and e["score"] >= T.NOTIFY_MIN_SCORE))]
        if urgent:
            urgent.sort(key=lambda e: (not e["priority"], -e["score"]))
            extra = len(urgent) - 25
            with open(os.path.join(NOTIFY_DIR, "urgent.md"), "w") as f:
                f.write(f"{len(urgent)} new event(s) you should see now.\n\n")
                f.write("\n".join(line(e) for e in urgent[:25]))
                if extra > 0:
                    f.write(f"\n\n…and {extra} more — open the site and sort by "
                            f"'recently found'.")

    # weekly digest (Mondays, or forced)
    if os.environ.get("EH_DIGEST") or today().weekday() == 0:
        week = (today() - dt.timedelta(days=7)).isoformat()
        fresh = [e for e in events if e.get("first_seen", t) >= week
                 and e["score"] >= T.NOTIFY_MIN_SCORE]
        soon_dl = [e for e in events if e.get("deadline") and t <= e["deadline"] <=
                   (today() + dt.timedelta(days=21)).isoformat() and e["score"] >= T.NOTIFY_MIN_SCORE]
        if fresh or soon_dl:
            parts = [f"Weekly digest — {len(fresh)} new relevant event(s) found in the last 7 days.\n"]
            if soon_dl:
                parts.append("## Deadlines in the next 3 weeks\n" +
                             "\n".join(line(e) for e in sorted(soon_dl, key=lambda e: e["deadline"])))
            for fid, flabel in T.FIELDS.items():
                grp = [e for e in fresh if e["fields"] and e["fields"][0] == fid]
                if grp:
                    parts.append(f"## {flabel}\n" + "\n".join(
                        line(e) for e in sorted(grp, key=lambda e: (-e["score"], e["start_date"] or ""))))
            with open(os.path.join(NOTIFY_DIR, "digest.md"), "w") as f:
                f.write("\n\n".join(parts))

    # source health: only when something newly breaks (no daily nagging)
    broken = [h for h in health if h["status"] in ("error", "empty")
              and h.get("previous") not in ("error", "empty")]
    if broken:
        with open(os.path.join(NOTIFY_DIR, "health.md"), "w") as f:
            f.write("These sources stopped returning events:\n\n" + "\n".join(
                f"- **{h['name']}** — {h['status']} {h['message']}" for h in broken))


def main():
    prev = load_previous()
    prev_events = {e["id"]: e for e in prev.get("events", []) if "id" in e}
    raw, health = run_sources(prev.get("health"))
    events = dedupe(normalise(raw))
    status = classify_all(events)

    t = today().isoformat()
    for e in events:
        e["first_seen"] = prev_events.get(e["id"], {}).get("first_seen", t)
        e["description"] = (e["description"] or "")[:280]
        e.pop("declared", None)
    kept = {}
    for e in events:
        for s in e["sources"]:
            kept[s] = kept.get(s, 0) + 1
    for h in health:
        h["kept"] = kept.get(h["name"], 0)

    events.sort(key=lambda e: (not e["priority"], e["start_date"] or "9999", -e["score"]))
    os.makedirs(os.path.dirname(EVENTS), exist_ok=True)
    with open(EVENTS, "w") as f:
        json.dump({"version": 5.1,
                   "generated": dt.datetime.now(dt.timezone.utc).isoformat(),
                   "taxonomy": T.export_for_frontend(),
                   "health": health, "classifiers": status,
                   "events": events}, f, ensure_ascii=False, separators=(",", ":"))
    notifications(events, set(prev_events), health)
    n_cls = sum(1 for e in events if e["fields"])
    print(f"\nWrote {len(events)} events ({n_cls} classified) -> docs/events.json")
    print("Classifiers:", json.dumps(status))


if __name__ == "__main__":
    main()
