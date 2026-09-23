import os
from listing import extract_listing

FX = os.path.join(os.path.dirname(__file__), "fixtures")

def test_icts_menu_links_rejected():
    ev = extract_listing("https://www.icts.res.in/programs/upcoming", "ICTS", "ICTS, Bengaluru",
                         href_filter=r"/(program|discussion-meeting|event|lectures|school)",
                         html=open(os.path.join(FX, "icts_like.html")).read())
    titles = {e["title"] for e in ev}
    assert titles == {"Fifty years of Eisenstein ideal", "Recent advances in low-dimensional topology"}
    assert all(e["start_date"] for e in ev)          # undated items never pass

def test_rri_layout_and_year_rollover():
    ev = extract_listing("https://www.rri.res.in/meetings", "RRI", "RRI, Bengaluru",
                         html=open(os.path.join(FX, "rri_like.html")).read())
    by = {e["title"]: (e["start_date"], e["end_date"]) for e in ev}
    assert by["Rethinking Cosmology"] == ("2027-12-08", "2027-12-12")
    assert by["Women at the Intersection of Mathematics and Theoretical Physics"] == ("2027-12-29", "2028-01-02")
    assert "Load More" not in by
