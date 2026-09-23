import datetime as dt
import scrape as S

T0 = dt.date.today()
d = lambda n: (T0 + dt.timedelta(days=n)).isoformat()

def raw(title, start, end=None, **kw):
    base = dict(title=title, url="https://x.org/" + title.replace(" ", "-"), start_date=start,
                end_date=end, deadline=None, location=kw.pop("location", None), country=None,
                online=False, tz=None, description="", speaker=None, source=kw.pop("source", "S"),
                raw_type=None, declared=[], priority=kw.pop("priority", False))
    base.update(kw)
    return base

def test_past_and_undated_dropped():
    out = S.normalise([raw("Past cosmology meeting", d(-10), d(-5)),
                       raw("Undated menu item", None),
                       raw("Ongoing cosmology school", d(-2), d(3)),
                       raw("Future dark energy workshop", d(30))])
    assert {e["title"] for e in out} == {"Ongoing cosmology school", "Future dark energy workshop"}

def test_pinned_undated_kept():
    out = S.normalise([raw("A microsite I care about", None, priority=True, source="Watchlist")])
    assert len(out) == 1

def test_nav_titles_dropped():
    assert S.normalise([raw("Past programs", d(5)), raw("Program Committee", d(5))]) == []

def test_cross_source_dedupe():
    ev = S.normalise([
        raw("12th KIAS Workshop on Cosmology and Structure Formation", d(40), source="CADC Astronomy Meetings", location="Seoul"),
        raw("KIAS Workshop on Cosmology and Structure Formation 12th", d(40), source="INSPIRE conferences"),
        raw("The 12th KIAS Workshop on Cosmology and Structure Formation", d(40), source="DESC Cosmology Meetings", description="long description here"),
    ])
    out = S.dedupe(ev)
    assert len(out) == 1
    assert set(out[0]['sources']) == {'CADC Astronomy Meetings', 'INSPIRE conferences', 'DESC Cosmology Meetings'}
    merged = [e for e in out if "DESC Cosmology Meetings" in e["sources"]][0]
    assert merged["source"] == "DESC Cosmology Meetings"     # curated source preferred
    assert merged["region"] == "abroad"                      # location merged from CADC copy

def test_types():
    assert S.classify_type("Winter School on Biological Physics", None, "x") == "School"
    assert S.classify_type("Discussion meeting on topology", None, "x") == "Workshop"
    assert S.classify_type("Colloquium: dark matter", None, "x") == "Talk / Seminar"

def test_distinct_events_same_day_not_merged():
    ev = S.normalise([raw("Dark energy workshop", d(20)), raw("Dark matter workshop", d(20))])
    assert len(S.dedupe(ev)) == 2
