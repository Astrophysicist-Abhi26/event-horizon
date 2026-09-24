"""v5.2: page layouts found on the live institute sites (captured 2026-09-24)."""
import datetime as dt
import os

import sources_india as SI
from common import parse_date_range
from listing import extract_listing

FX = os.path.join(os.path.dirname(__file__), "fixtures")


def _read(n):
    with open(os.path.join(FX, n)) as f:
        return f.read()


def test_range_with_comma_before_year():
    assert parse_date_range("Date: 13 – 17 December, 2025") == ("2025-12-13", "2025-12-17")
    assert parse_date_range("30 Nov - 4 Dec, 2026") == ("2026-11-30", "2026-12-04")


def test_generic_website_link_takes_title_from_heading():
    evs = extract_listing("https://physics.iisc.ac.in/events-all/conferences/", "IISc", "IISc",
                          html=_read("iisc_physics_like.html"))
    got = {e["title"]: (e["start_date"], e["end_date"]) for e in evs}
    assert got["ICMS 2031"] == ("2031-10-04", "2031-10-08")
    assert got["Online Winter School on Matter, Life & Cosmos"] == ("2031-12-13", "2031-12-17")
    assert len(evs) == 2


def test_image_link_uses_alt_text():
    evs = extract_listing("https://www.iucaa.in/en/other-info/9-upcoming-events-at-iucaa",
                          "IUCAA", "IUCAA, Pune, India", html=_read("iucaa_like.html"))
    got = {e["title"]: (e["start_date"], e["end_date"]) for e in evs}
    assert got["LIGO-Virgo-Kagra (LVK) Collaboration Meeting"] == ("2031-09-21", "2031-09-25")
    assert got["ML4GW+Controls Workshop @ LVK"] == ("2031-09-25", "2031-09-25")


def test_accordion_header_titles_kept_and_posted_dates_ignored():
    evs = extract_listing("https://www.astron-soc.in/announcement", "ASI", "India",
                          html=_read("asi_like.html"))
    assert [(e["title"][:22], e["start_date"], e["end_date"]) for e in evs] == \
        [("Young Astronomers' Mee", "2031-12-21", "2031-12-23")]   # deadline notice dropped


def test_indico_falls_back_to_ical_when_export_needs_key(monkeypatch):
    day = dt.date.today() + dt.timedelta(days=30)
    ics = ("BEGIN:VCALENDAR\nBEGIN:VEVENT\nSUMMARY:The Microwave Sky [Astrophysics Seminar]\n"
           f"DTSTART:{day:%Y%m%d}T053000Z\nDTEND:{day:%Y%m%d}T063000Z\n"
           "URL:https://events.iiap.res.in/event/473/\nEND:VEVENT\nEND:VCALENDAR\n")

    class R:
        def __init__(self, url):
            self.url = url
            self.text = ics

        def json(self):
            raise ValueError("Expecting value")          # HTML / "API key is missing"

    monkeypatch.setattr(SI, "get", lambda url, **kw: R(url))
    evs = SI._indico({"name": "IIA", "base": "https://events.iiap.res.in", "category": 6,
                      "location": "IIA, Bengaluru, India"})
    assert [(e["title"], e["start_date"], e["url"]) for e in evs] == \
        [("The Microwave Sky [Astrophysics Seminar]", day.isoformat(), "https://events.iiap.res.in/event/473/")]


def test_feed_sources_may_be_empty_without_alarm():
    names = SI.empty_ok_names()
    assert "IIA seminars & colloquia" in names and "IISc EE events" in names
    assert "RRI talks" not in names                 # an empty HTML listing may mean breakage


def test_researchseminars_conferences_filtered_locally(monkeypatch):
    import datetime as _d
    import sources as G
    soon = (_d.date.today() + _d.timedelta(days=20)).isoformat()
    past = (_d.date.today() - _d.timedelta(days=20)).isoformat()
    seen = {}

    class R:
        def json(self):
            return {"results": [
                {"name": "Cosmology on the Beach", "shortname": "cob", "topics": ["astro_CO"],
                 "start_date": soon, "end_date": soon},
                {"name": "Old meeting", "shortname": "old", "topics": ["astro_CO"],
                 "start_date": past, "end_date": past},
                {"name": "Botany days", "shortname": "bot", "topics": ["bio_PE"],
                 "start_date": soon, "end_date": soon}]}

    def fake_get(url, params=None, **kw):
        seen.update(params or {})
        return R()

    monkeypatch.setattr(G, "get", fake_get)
    evs = G.scrape_researchseminars_conferences()
    assert [e["title"] for e in evs] == ["Cosmology on the Beach"]
    assert not any(k in seen for k in ("end_date", "start_date"))   # no server-side date filter
