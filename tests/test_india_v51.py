"""v5.1: Bengaluru/India coverage — adapters, date formats, manual intake."""
import json
import os

import sources_india as SI
from common import parse_date_range
from listing import extract_listing

FX = os.path.join(os.path.dirname(__file__), "fixtures")
CFG = {"name": "T", "location": "Somewhere, Bengaluru, India"}


def _read(n):
    with open(os.path.join(FX, n)) as f:
        return f.read()


def test_day_first_numeric_dates():
    assert parse_date_range("01/02/2027 05/02/2027") == ("2027-02-01", "2027-02-05")
    assert parse_date_range("on 17.11.2026") == ("2026-11-17", "2026-11-17")
    assert parse_date_range("31/02/2027") == (None, None)       # impossible -> no guess


def test_rri_rows_with_youtube_link_are_kept():
    evs = extract_listing("https://www.rri.res.in/events", "RRI talks",
                          "Raman Research Institute, Bengaluru, India",
                          href_filter=r"rri\.res\.in/events/[a-z0-9]+(?:-[a-z0-9]+){3,}$"
                                      r"|^/events/[a-z0-9]+(?:-[a-z0-9]+){3,}$",
                          html=_read("rri_talks_like.html"))
    got = {e["title"]: e["start_date"] for e in evs}
    assert got.get("An Arctic Window into the Ultra-Low Frequency Universe") == "2031-10-08"
    # this row also carries a YouTube link; v5 dropped it as a "list container"
    assert any(t.startswith("What is modern about Gandhi") for t in got)
    assert all("Load More" not in t and "Meetings" not in t for t in got)


def test_jncasr_table_numeric_dates():
    evs = extract_listing("https://www.jncasr.ac.in/all-events", "JNCASR events", "JNCASR",
                          href_filter=r"/all-events/[a-z0-9-]{12,}", html=_read("jncasr_like.html"))
    assert len(evs) == 1
    assert (evs[0]["start_date"], evs[0]["end_date"]) == ("2031-02-01", "2031-02-05")


import datetime as _dt
SOON = (_dt.date.today() + _dt.timedelta(days=30))
ICS = """BEGIN:VCALENDAR
X-WR-CALNAME:Astronomy & Astrophysics Seminars
BEGIN:VEVENT
SUMMARY:Constraining dynamical dark energy with DESI
DTSTART:{d}T103000Z
DTEND:{d}T113000Z
LOCATION:Auditorium\\, Physics
DESCRIPTION:Speaker: A. Person
END:VEVENT
BEGIN:VEVENT
SUMMARY:Old talk
DTSTART:20200115T103000Z
END:VEVENT
BEGIN:VEVENT
SUMMARY:Weekly cosmology journal club
DTSTART:20200101T100000
RRULE:FREQ=WEEKLY;BYDAY=TH
END:VEVENT
END:VCALENDAR
""".replace("{d}", SOON.strftime("%Y%m%d"))


def test_ical_calendar_name_past_and_recurrence():
    evs = SI.ical_events(dict(CFG, page="https://physics.iisc.ac.in/calendar/"), ICS)
    titles = [e["title"] for e in evs]
    assert "Constraining dynamical dark energy with DESI" in titles
    assert "Old talk" not in titles
    weekly = [e for e in evs if e["title"] == "Weekly cosmology journal club"]
    assert 1 <= len(weekly) <= SI.RECUR_MAX            # expanded, but capped
    desi = next(e for e in evs if "DESI" in e["title"])
    assert desi["start_date"] == SOON.isoformat()
    assert "Astronomy & Astrophysics Seminars" in desi["description"]
    assert desi["url"] == "https://physics.iisc.ac.in/calendar/"


def test_wordpress_events_json():
    data = {"events": [{"title": "Seminar: Scaling laws for neural operators",
                        "url": "https://ee.iisc.ac.in/event/x/",
                        "start_date": "2031-03-02 16:00:00", "end_date": "2031-03-02 17:00:00",
                        "description": "<p>Abstract</p>", "venue": {"venue": "MMCR", "city": "Bengaluru"},
                        "categories": [{"name": "Seminar"}]}]}
    evs = SI.wp_events_from_json(dict(CFG, base="https://ee.iisc.ac.in"), data)
    assert evs[0]["start_date"] == "2031-03-02" and evs[0]["location"] == "MMCR, Bengaluru"
    assert evs[0]["raw_type"] == "Seminar"


def test_issue_form_parsing():
    body = ("### Event name\n\nFourth Neighbourhood Cosmology Meeting\n\n"
            "### Link\n\n_No response_\n\n### Start date\n\n17 Nov 2026\n\n"
            "### End date\n\n_No response_\n\n### Registration / abstract deadline\n\n2026-10-20\n\n"
            "### Where\n\nCHRIST University, Bengaluru\n\n### Type\n\nConference\n\n"
            "### Research fields\n\n- [X] Cosmology (general)\n- [ ] Astrophysics\n- [X] ML for science\n\n"
            "### Notes\n\nFrom the group mailing list")
    it = SI.parse_issue_form("[Event] NCM4", body)
    assert it["title"] == "Fourth Neighbourhood Cosmology Meeting"
    assert it["start"] == "2026-11-17" and it["deadline"] == "2026-10-20"
    assert "url" not in it and it["type"] == "Conference"
    assert it["fields"] == ["cosmo.general", "ai.science"]


def test_registry_loads_and_every_kind_is_known():
    names = [n for n, _, _ in SI.india_sources(include_disabled=True)]
    assert len(names) == len(set(names)), "duplicate source names"
    assert any(n.startswith("IISc") for n in names) and "RRI talks" in names


def test_watchlist_ncm4_seeded():
    evs = SI.scrape_watchlist()
    assert any("Neighbourhood Cosmology" in e["title"] and e["start_date"] == "2026-11-17"
               for e in evs)
