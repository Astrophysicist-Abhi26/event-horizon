import pytest
from common import iso, parse_date_range

@pytest.mark.parametrize("text,expected", [
    ("06 July 2026 to 10 July 2026", ("2026-07-06", "2026-07-10")),
    ("November 30 - December 7, 2025", ("2025-11-30", "2025-12-07")),
    ("September 7–11, 2026", ("2026-09-07", "2026-09-11")),
    ("7-11 September 2026", ("2026-09-07", "2026-09-11")),
    ("30 Nov - 4 Dec 2026", ("2026-11-30", "2026-12-04")),
    ("Dec 28 - Jan 3, 2027", ("2026-12-28", "2027-01-03")),
    ("Monday 13, September 2027 to Friday 17, September 2027", ("2027-09-13", "2027-09-17")),  # CADC style
    ("2026-09-07 to 2026-09-11", ("2026-09-07", "2026-09-11")),   # ISO never day/month swapped
    ("May 12, 2026 at 02:30 PM", ("2026-05-12", "2026-05-12")),
])
def test_ranges(text, expected):
    assert parse_date_range(text) == expected

def test_no_invented_days():
    # v1-v4 bug class: a month-only date silently borrowed today's day number
    assert iso("June 2026") is None
    assert parse_date_range("Sep 2026 conference") == (None, None)
    assert parse_date_range("no date here 42") == (None, None)

def test_ical_basic_date():
    assert iso("20261012") == "2026-10-12"
    assert iso("20261012T090000Z") == "2026-10-12"
