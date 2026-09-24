"""
Where is an event?  -> country + region in {bengaluru, india, online, abroad, unknown}

Order of trust: a country/country-code given by the source > institute and
city names in the location text > generic country names.
"""

import re

BENGALURU = [
    "bengaluru", "bangalore", "iisc", "indian institute of science", "icts",
    "international centre for theoretical sciences", "raman research institute",
    r"\brri\b", "indian institute of astrophysics", r"\biia\b", "ncbs", "jncasr",
    "isro satellite", "ursc", r"\bnias\b", "iiit bangalore", "isi bangalore",
    "azim premji", "koramangala", "hesaraghatta", "sadashivanagar", "hebbal",
    "christ university", r"christ \(deemed", "jakkur", "st\\.? joseph'?s", "iiit-b",
]
INDIA = [
    "india", "mumbai", "pune", "delhi", "chennai", "kolkata", "hyderabad",
    "ahmedabad", "bhubaneswar", "mohali", "bhopal", "thiruvananthapuram",
    "trivandrum", "kanpur", "kharagpur", "guwahati", "allahabad", "prayagraj",
    "nainital", "mysuru", "mysore", "goa", "tirupati", "berhampur", "gandhinagar",
    "roorkee", "varanasi", "jaipur", "chandigarh", "indore", "kochi", "patna",
    "shillong", "srinagar", "udaipur", "dharwad", "manipal", "tifr", "iucaa",
    "ncra", "imsc", "iiser", r"\biit\b", r"\bprl\b", "harish-chandra", r"\bhri\b",
    "aries", "chennai mathematical", r"\bcmi\b", "s. n. bose", "sn bose",
    "institute of physics, bhubaneswar", "niser", "iacs", "saha institute",
    "isi kolkata", "iist", "tata institute",
]
ONLINE = [r"\bonline\b", r"\bvirtual\b", r"\bzoom\b", r"\bwebinar\b", r"\bremote\b",
          r"\bgoogle meet\b", r"\bmicrosoft teams\b"]

COUNTRY_CODES = {
    "IN": "India", "US": "USA", "GB": "UK", "UK": "UK", "DE": "Germany",
    "FR": "France", "IT": "Italy", "ES": "Spain", "NL": "Netherlands",
    "CH": "Switzerland", "AT": "Austria", "BE": "Belgium", "SE": "Sweden",
    "NO": "Norway", "DK": "Denmark", "FI": "Finland", "PL": "Poland",
    "PT": "Portugal", "GR": "Greece", "IE": "Ireland", "CZ": "Czechia",
    "HU": "Hungary", "JP": "Japan", "CN": "China", "KR": "South Korea",
    "TW": "Taiwan", "SG": "Singapore", "AU": "Australia", "NZ": "New Zealand",
    "CA": "Canada", "MX": "Mexico", "BR": "Brazil", "AR": "Argentina",
    "CL": "Chile", "ZA": "South Africa", "IL": "Israel", "TR": "Turkey",
    "RU": "Russia", "AE": "UAE", "SA": "Saudi Arabia", "TH": "Thailand",
    "VN": "Vietnam", "ID": "Indonesia", "MY": "Malaysia", "HK": "Hong Kong",
    "KE": "Kenya", "EG": "Egypt", "SK": "Slovakia", "SI": "Slovenia",
    "RS": "Serbia", "HR": "Croatia", "RO": "Romania", "BG": "Bulgaria",
    "EE": "Estonia", "LT": "Lithuania", "LV": "Latvia", "UA": "Ukraine",
    "IR": "Iran", "PK": "Pakistan", "BD": "Bangladesh", "LK": "Sri Lanka",
    "NP": "Nepal", "PH": "Philippines", "CO": "Colombia", "PE": "Peru",
    "UY": "Uruguay", "LU": "Luxembourg", "IS": "Iceland", "CY": "Cyprus",
    "MT": "Malta", "MA": "Morocco", "NG": "Nigeria", "ET": "Ethiopia",
}
COUNTRY_NAMES = {
    "united states": "USA", "usa": "USA", "u.s.a": "USA", "united kingdom": "UK",
    "england": "UK", "scotland": "UK", "wales": "UK", "germany": "Germany",
    "france": "France", "italy": "Italy", "spain": "Spain",
    "netherlands": "Netherlands", "the netherlands": "Netherlands",
    "switzerland": "Switzerland", "austria": "Austria", "belgium": "Belgium",
    "sweden": "Sweden", "norway": "Norway", "denmark": "Denmark",
    "finland": "Finland", "poland": "Poland", "portugal": "Portugal",
    "greece": "Greece", "ireland": "Ireland", "czech": "Czechia",
    "hungary": "Hungary", "japan": "Japan", "china": "China",
    "south korea": "South Korea", "korea": "South Korea", "taiwan": "Taiwan",
    "singapore": "Singapore", "australia": "Australia",
    "new zealand": "New Zealand", "canada": "Canada", "mexico": "Mexico",
    "brazil": "Brazil", "argentina": "Argentina", "chile": "Chile",
    "south africa": "South Africa", "israel": "Israel", "turkey": "Turkey",
    "türkiye": "Turkey", "russia": "Russia", "uae": "UAE",
    "united arab emirates": "UAE", "saudi arabia": "Saudi Arabia",
    "thailand": "Thailand", "vietnam": "Vietnam", "viet nam": "Vietnam",
    "indonesia": "Indonesia", "malaysia": "Malaysia", "hong kong": "Hong Kong",
    "kenya": "Kenya", "egypt": "Egypt", "slovak": "Slovakia",
    "slovenia": "Slovenia", "serbia": "Serbia", "croatia": "Croatia",
    "romania": "Romania", "bulgaria": "Bulgaria", "estonia": "Estonia",
    "iran": "Iran", "sri lanka": "Sri Lanka", "nepal": "Nepal",
    "philippines": "Philippines", "colombia": "Colombia", "peru": "Peru",
    "luxembourg": "Luxembourg", "iceland": "Iceland", "cyprus": "Cyprus",
    "morocco": "Morocco", "nigeria": "Nigeria", "ukraine": "Ukraine",
}
CITIES = {
    "boston": "USA", "cambridge, ma": "USA", "new york": "USA", "chicago": "USA",
    "pasadena": "USA", "berkeley": "USA", "stanford": "USA", "princeton": "USA",
    "seattle": "USA", "san francisco": "USA", "san diego": "USA", "los angeles": "USA",
    "austin": "USA", "pittsburgh": "USA", "philadelphia": "USA", "baltimore": "USA",
    "washington": "USA", "denver": "USA", "boulder": "USA", "honolulu": "USA",
    "nashville": "USA", "anaheim": "USA", "santa barbara": "USA", "aspen": "USA",
    "ann arbor": "USA", "atlanta": "USA", "miami": "USA", "orlando": "USA",
    "tucson": "USA", "phoenix": "USA", "albuquerque": "USA", "waikoloa": "USA",
    "vancouver": "Canada", "toronto": "Canada", "montreal": "Canada",
    "montréal": "Canada", "waterloo": "Canada", "ottawa": "Canada",
    "london": "UK", "oxford": "UK", "cambridge, uk": "UK", "edinburgh": "UK",
    "manchester": "UK", "durham": "UK", "southampton": "UK", "leeds": "UK",
    "paris": "France", "lyon": "France", "marseille": "France", "nice": "France",
    "strasbourg": "France", "toulouse": "France", "grenoble": "France",
    "berlin": "Germany", "munich": "Germany", "münchen": "Germany",
    "heidelberg": "Germany", "garching": "Germany", "bonn": "Germany",
    "hamburg": "Germany", "potsdam": "Germany", "göttingen": "Germany",
    "amsterdam": "Netherlands", "leiden": "Netherlands", "utrecht": "Netherlands",
    "noordwijk": "Netherlands", "maastricht": "Netherlands", "groningen": "Netherlands",
    "zurich": "Switzerland", "zürich": "Switzerland", "geneva": "Switzerland",
    "lausanne": "Switzerland", "saas-fee": "Switzerland", "saas fee": "Switzerland",
    "vienna": "Austria", "rome": "Italy", "milan": "Italy", "trieste": "Italy",
    "florence": "Italy", "padova": "Italy", "padua": "Italy", "bologna": "Italy",
    "naples": "Italy", "turin": "Italy", "torino": "Italy", "lucca": "Italy",
    "madrid": "Spain", "barcelona": "Spain", "tenerife": "Spain", "valencia": "Spain",
    "lisbon": "Portugal", "porto": "Portugal", "stockholm": "Sweden", "lund": "Sweden",
    "copenhagen": "Denmark", "helsinki": "Finland", "prague": "Czechia",
    "budapest": "Hungary", "warsaw": "Poland", "krakow": "Poland",
    "athens": "Greece", "thessaloniki": "Greece", "dublin": "Ireland",
    "tokyo": "Japan", "kyoto": "Japan", "osaka": "Japan", "nagoya": "Japan",
    "kashiwa": "Japan", "beijing": "China", "shanghai": "China", "shenyang": "China",
    "hefei": "China", "nanjing": "China", "seoul": "South Korea", "daejeon": "South Korea",
    "taipei": "Taiwan", "sydney": "Australia", "melbourne": "Australia",
    "canberra": "Australia", "perth": "Australia", "brisbane": "Australia",
    "hobart": "Australia", "santiago": "Chile", "la serena": "Chile",
    "bariloche": "Argentina", "buenos aires": "Argentina",
    "rio de janeiro": "Brazil", "são paulo": "Brazil", "sao paulo": "Brazil",
    "cape town": "South Africa", "johannesburg": "South Africa",
    "tel aviv": "Israel", "jerusalem": "Israel", "istanbul": "Turkey",
    "antalya": "Turkey", "abu dhabi": "UAE", "dubai": "UAE",
    "kuala lumpur": "Malaysia", "hanoi": "Vietnam", "bangkok": "Thailand",
    # well-known research institutes that often appear without a city
    "flatiron": "USA", "kitp": "USA", "kavli institute for theoretical physics": "USA",
    "caltech": "USA", "harvard": "USA", "mit": "USA", "fermilab": "USA", "slac": "USA",
    "institute for advanced study": "USA", "stsci": "USA",
    "perimeter institute": "Canada", "cita": "Canada", "ictp": "Italy", "sissa": "Italy",
    "gssi": "Italy", "cern": "Switzerland", "epfl": "Switzerland", "eth": "Switzerland",
    "eso": "Germany", "max planck": "Germany", "mpia": "Germany", "mpa": "Germany",
    "desy": "Germany", "iap": "France", "ihes": "France", "ihp": "France",
    "nordita": "Sweden", "niels bohr": "Denmark", "dias": "Ireland", "estec": "Netherlands",
    "kavli ipmu": "Japan", "ipmu": "Japan", "yukawa": "Japan", "kias": "South Korea",
    "kasi": "South Korea", "ibs": "South Korea", "tsinghua": "China", "sjtu": "China",
    "kavli iaa": "China", "aspen": "USA", "banff": "Canada", "birs": "Canada",
    "oberwolfach": "Germany", "les houches": "France", "cargese": "France",
    "benasque": "Spain", "erice": "Italy", "lorentz center": "Netherlands",
}

_B = [re.compile(p, re.I) for p in BENGALURU]
_I = [re.compile(p, re.I) for p in INDIA]
_O = [re.compile(p, re.I) for p in ONLINE]


def _any(pats, text):
    return any(p.search(text) for p in pats)


def locate(location, country_hint=None, online_hint=False, tz_hint=None):
    """-> (country or None, region, online: bool)"""
    loc = (location or "").strip()
    low = loc.lower()
    online = bool(online_hint) or _any(_O, low)
    country = None
    if country_hint:
        ch = str(country_hint).strip()
        country = COUNTRY_CODES.get(ch.upper()) or COUNTRY_NAMES.get(ch.lower()) or ch
    if low:
        if _any(_B, low):
            return "India", "bengaluru", online
        if country is None and _any(_I, low):
            country = "India"
        if country is None:
            for name, c in sorted(COUNTRY_NAMES.items(), key=lambda x: -len(x[0])):
                if re.search(r"\b" + re.escape(name) + r"\b", low):
                    country = c
                    break
        if country is None:
            for city, c in CITIES.items():
                if re.search(r"\b" + re.escape(city) + r"\b", low):
                    country = c
                    break
        if country is None and re.search(r",\s*[A-Z]{2}\b", loc) and not online:
            country = "USA"  # "Tucson, AZ"
    if country is None and tz_hint and re.search(r"Asia/(Kolkata|Calcutta)", tz_hint) \
            and not online:
        country = "India"
    if country == "India":
        return country, "india", online
    if country:
        return country, "abroad", online
    if online:
        return "Online", "online", True
    return None, "unknown", online
