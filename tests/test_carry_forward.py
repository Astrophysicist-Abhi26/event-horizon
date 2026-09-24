"""v5.3: a source that is down today keeps its last good upcoming events."""
import datetime as dt

import scrape as S

D = lambda n: (dt.date.today() + dt.timedelta(days=n)).isoformat()
NOW = lambda h=0: (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=h)).isoformat()

PREV_EVENTS = [
    dict(title="ICMS 2026", url="https://x/icms", start_date=D(10), end_date=D(14),
         location="IISc, Bengaluru, India", country="India", type="Conference",
         source="IISc Physics (conferences)", sources=["IISc Physics (conferences)"],
         description="Molecular simulation", priority=False),
    dict(title="Long gone", url="https://x/old", start_date=D(-20), end_date=D(-18),
         source="IISc Physics (conferences)", sources=["IISc Physics (conferences)"]),
    dict(title="Someone else's", url="https://x/other", start_date=D(5), end_date=D(5),
         source="RRI talks", sources=["RRI talks"]),
]


def _run(monkeypatch, fn, prev_health):
    monkeypatch.setattr(S, "GLOBAL_SOURCES", [])
    monkeypatch.setattr(S, "india_sources", lambda: [("IISc Physics (conferences)", fn, 0)])
    monkeypatch.setattr(S, "scrape_watchlist", lambda: [])
    monkeypatch.setattr(S, "scrape_issue_intake", lambda: [])
    raw, health = S.run_sources(prev_health, PREV_EVENTS)
    return raw, {h["name"]: h for h in health}["IISc Physics (conferences)"]


def _boom():
    raise RuntimeError("too many 502 error responses")


def test_error_carries_last_good_upcoming_events(monkeypatch):
    prev = [dict(name="IISc Physics (conferences)", status="ok", raw=3, last_ok=NOW(3))]
    raw, h = _run(monkeypatch, _boom, prev)
    assert h["status"] == "stale" and "502" in h["message"]
    assert [e["title"] for e in raw] == ["ICMS 2026"]            # past + other sources excluded
    assert h["last_ok"] == prev[0]["last_ok"]                     # not refreshed by a carry
    ev = S.normalise(raw)[0]
    assert ev["region"] == "bengaluru" and ev["type"] == "Conference"


def test_sudden_empty_page_also_carries(monkeypatch):
    prev = [dict(name="IISc Physics (conferences)", status="ok", raw=3, last_ok=NOW(3))]
    raw, h = _run(monkeypatch, lambda: [], prev)
    assert h["status"] == "stale" and len(raw) == 1


def test_no_carry_after_two_weeks(monkeypatch):
    prev = [dict(name="IISc Physics (conferences)", status="stale", raw=1,
                 last_ok=NOW(24 * (S.CARRY_MAX_DAYS + 1)))]
    raw, h = _run(monkeypatch, _boom, prev)
    assert h["status"] == "error" and raw == []


def test_empty_page_that_was_already_empty_stays_empty(monkeypatch):
    prev = [dict(name="IISc Physics (conferences)", status="empty", raw=0, last_ok=NOW(3))]
    raw, h = _run(monkeypatch, lambda: [], prev)
    assert h["status"] == "empty" and raw == []
