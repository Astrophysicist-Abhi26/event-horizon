from geo import locate

def test_regions():
    assert locate("ICTS, Bengaluru, India")[1] == "bengaluru"
    assert locate("Raman Research Institute")[1] == "bengaluru"
    assert locate("IMSc, Chennai")[1] == "india"
    assert locate("Online")[1] == "online"
    assert locate("Tucson, AZ")[:2] == ("USA", "abroad")
    assert locate(None, "IN")[1] == "india"
    assert locate("Room 204", tz_hint="Asia/Kolkata")[1] == "india"
    assert locate("PhD student")[1] == "unknown"      # v1-v4 used speaker affiliation as location

def test_hybrid_keeps_physical_place():
    country, region, online = locate("Hybrid: IUCAA Pune + Zoom")
    assert (region, online) == ("india", True)
