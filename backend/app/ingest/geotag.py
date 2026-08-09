"""
Rule-based classifier: takes article title+summary text and decides
  - which AO it belongs to (or None)
  - a representative lat/lon to plot it at
  - a country label
  - a SIGACT category
  - a heuristic severity 1-5
  - whether it clears the bar to be a "SIGACT" at all vs. background noise

This is intentionally transparent and hand-tunable rather than a trained NER
model — edit the keyword lists below to match your PIRs (priority
intelligence requirements). Matching is case-insensitive substring matching
over title + summary.
"""
from dataclasses import dataclass
import re
from typing import Optional

CLASSIFIER_VERSION = 5

# ---------------------------------------------------------------------------
# Location gazetteer: place name -> (lat, lon, country, AO)
# ---------------------------------------------------------------------------
GAZETTEER = {
    # AO_HIGH_NORTH — High North, Finland and the Baltic states
    "tallinn": (59.437, 24.7536, "Estonia", "AO_HIGH_NORTH"),
    "tartu": (58.3776, 26.729, "Estonia", "AO_HIGH_NORTH"),
    "estonia": (58.5953, 25.0136, "Estonia", "AO_HIGH_NORTH"),
    "riga": (56.9496, 24.1052, "Latvia", "AO_HIGH_NORTH"),
    "latvia": (56.8796, 24.6032, "Latvia", "AO_HIGH_NORTH"),
    "vilnius": (54.6872, 25.2797, "Lithuania", "AO_HIGH_NORTH"),
    "kaunas": (54.8985, 23.9036, "Lithuania", "AO_HIGH_NORTH"),
    "klaipeda": (55.7033, 21.1443, "Lithuania", "AO_HIGH_NORTH"),
    "lithuania": (55.1694, 23.8813, "Lithuania", "AO_HIGH_NORTH"),
    "kaliningrad": (54.7104, 20.4522, "Russia (Kaliningrad)", "AO_HIGH_NORTH"),
    "suwalki": (54.1000, 22.9300, "Poland/Lithuania border", "AO_HIGH_NORTH"),
    "helsinki": (60.1699, 24.9384, "Finland", "AO_HIGH_NORTH"),
    "rovaniemi": (66.5039, 25.7294, "Finland", "AO_HIGH_NORTH"),
    "oulu": (65.0121, 25.4651, "Finland", "AO_HIGH_NORTH"),
    "finland": (61.9241, 25.7482, "Finland", "AO_HIGH_NORTH"),
    "gulf of finland": (59.8, 25.5, "Baltic Sea", "AO_HIGH_NORTH"),
    "gulf of bothnia": (62.5, 19.5, "Baltic Sea", "AO_HIGH_NORTH"),
    "baltic sea": (58.0, 19.5, "Baltic Sea", "AO_HIGH_NORTH"),
    "aland": (60.1785, 19.9156, "Finland (Åland)", "AO_HIGH_NORTH"),
    "norway": (60.472, 8.4689, "Norway", "AO_HIGH_NORTH"),
    "oslo": (59.9139, 10.7522, "Norway", "AO_HIGH_NORTH"),
    "svalbard": (78.2232, 15.6267, "Norway (Svalbard)", "AO_HIGH_NORTH"),
    "barents sea": (74.0, 36.0, "Barents Sea", "AO_HIGH_NORTH"),
    "arctic": (75.0, 40.0, "High North", "AO_HIGH_NORTH"),
    "murmansk": (68.9585, 33.0827, "Russia (Murmansk)", "AO_HIGH_NORTH"),
    "kola peninsula": (67.7, 33.8, "Russia (Kola)", "AO_HIGH_NORTH"),
    "gotland": (57.4, 18.5, "Sweden (Gotland)", "AO_HIGH_NORTH"),
    "stockholm": (59.3293, 18.0686, "Sweden", "AO_HIGH_NORTH"),
    "sweden": (60.1282, 18.6435, "Sweden", "AO_HIGH_NORTH"),
    "denmark": (56.2639, 9.5018, "Denmark", "AO_HIGH_NORTH"),
    "iceland": (64.9631, -19.0208, "Iceland", "AO_HIGH_NORTH"),
    "greenland": (71.7069, -42.6043, "Greenland", "AO_HIGH_NORTH"),
    "nuuk": (64.1814, -51.6941, "Greenland", "AO_HIGH_NORTH"),
    "tromso": (69.6492, 18.9553, "Norway", "AO_HIGH_NORTH"),
    "tromsø": (69.6492, 18.9553, "Norway", "AO_HIGH_NORTH"),
    "finnmark": (70.483, 26.013, "Norway", "AO_HIGH_NORTH"),
    "kirkenes": (69.7269, 30.045, "Norway", "AO_HIGH_NORTH"),
    "st petersburg": (59.9311, 30.3609, "Russia", "AO_HIGH_NORTH"),
    "amari": (59.2625, 24.2081, "Estonia (Ämari AB)", "AO_HIGH_NORTH"),
    "rukla": (55.0667, 24.2333, "Lithuania (Rukla garrison)", "AO_HIGH_NORTH"),
    "keflavik": (63.985, -22.6056, "Iceland (Keflavík)", "AO_HIGH_NORTH"),
    "baltic sentry": (58.0, 19.5, "Baltic Sea (NATO op)", "AO_HIGH_NORTH"),
    "bornholm": (55.1, 14.9, "Denmark (Bornholm)", "AO_HIGH_NORTH"),
    "nord stream": (55.0, 15.4, "Baltic Sea", "AO_HIGH_NORTH"),

    # AO_EUROPE — Ukraine and eastern / central Europe
    "ukraine": (48.3794, 31.1656, "Ukraine", "AO_EUROPE"),
    "kyiv": (50.4501, 30.5234, "Ukraine", "AO_EUROPE"),
    "sumy": (50.9077, 34.7981, "Ukraine", "AO_EUROPE"),
    "kharkiv": (49.9935, 36.2304, "Ukraine", "AO_EUROPE"),
    "odesa": (46.4825, 30.7233, "Ukraine", "AO_EUROPE"),
    "odessa": (46.4825, 30.7233, "Ukraine", "AO_EUROPE"),
    "dnipro": (48.4647, 35.0462, "Ukraine", "AO_EUROPE"),
    "zaporizhzhia": (47.8388, 35.1396, "Ukraine", "AO_EUROPE"),
    "kherson": (46.6354, 32.6169, "Ukraine", "AO_EUROPE"),
    "donetsk": (48.0159, 37.8029, "Ukraine", "AO_EUROPE"),
    "crimea": (45.3, 34.0, "Ukraine (Crimea)", "AO_EUROPE"),
    "black sea": (43.2, 34.0, "Black Sea", "AO_EUROPE"),
    "sea of azov": (46.1, 36.8, "Sea of Azov", "AO_EUROPE"),
    "poland": (51.9194, 19.1451, "Poland", "AO_EUROPE"),
    "warsaw": (52.2297, 21.0122, "Poland", "AO_EUROPE"),
    "belarus": (53.7098, 27.9534, "Belarus", "AO_EUROPE"),
    "minsk": (53.9006, 27.559, "Belarus", "AO_EUROPE"),
    "zapad": (55.75, 37.6, "Russia/Belarus (exercise)", "AO_EUROPE"),
    "mechernich": (50.593, 6.652, "Germany", "AO_EUROPE"),
    "leipzig": (51.3397, 12.3731, "Germany", "AO_EUROPE"),
    "germany": (51.1657, 10.4515, "Germany", "AO_EUROPE"),
    "austria": (47.5162, 14.5501, "Austria", "AO_EUROPE"),
    "vienna": (48.2082, 16.3738, "Austria", "AO_EUROPE"),
    "czech republic": (49.8175, 15.473, "Czechia", "AO_EUROPE"),
    "czechia": (49.8175, 15.473, "Czechia", "AO_EUROPE"),
    "prague": (50.0755, 14.4378, "Czechia", "AO_EUROPE"),
    "slovakia": (48.669, 19.699, "Slovakia", "AO_EUROPE"),
    "bratislava": (48.1486, 17.1077, "Slovakia", "AO_EUROPE"),
    "hungary": (47.1625, 19.5033, "Hungary", "AO_EUROPE"),
    "budapest": (47.4979, 19.0402, "Hungary", "AO_EUROPE"),
    "romania": (45.9432, 24.9668, "Romania", "AO_EUROPE"),
    "bucharest": (44.4268, 26.1025, "Romania", "AO_EUROPE"),
    "moldova": (47.4116, 28.3699, "Moldova", "AO_EUROPE"),
    "chisinau": (47.0105, 28.8638, "Moldova", "AO_EUROPE"),
    "chișinău": (47.0105, 28.8638, "Moldova", "AO_EUROPE"),
    "italy": (41.8719, 12.5674, "Italy", "AO_EUROPE"),
    "switzerland": (46.8182, 8.2275, "Switzerland", "AO_EUROPE"),
    "spain": (40.4637, -3.7492, "Spain", "AO_EUROPE"),
    "portugal": (39.3999, -8.2245, "Portugal", "AO_EUROPE"),

    # AO_BALKANS — Western Balkans and the south-eastern European flank
    "slovenia": (46.1512, 14.9955, "Slovenia", "AO_BALKANS"),
    "ljubljana": (46.0569, 14.5058, "Slovenia", "AO_BALKANS"),
    "croatia": (45.1, 15.2, "Croatia", "AO_BALKANS"),
    "zagreb": (45.815, 15.9819, "Croatia", "AO_BALKANS"),
    "split": (43.5081, 16.4402, "Croatia", "AO_BALKANS"),
    "dubrovnik": (42.6507, 18.0944, "Croatia", "AO_BALKANS"),
    "serbia": (44.0165, 21.0059, "Serbia", "AO_BALKANS"),
    "belgrade": (44.7866, 20.4489, "Serbia", "AO_BALKANS"),
    "bosnia": (43.9159, 17.6791, "Bosnia and Herzegovina", "AO_BALKANS"),
    "sarajevo": (43.8563, 18.4131, "Bosnia and Herzegovina", "AO_BALKANS"),
    "banja luka": (44.7722, 17.191, "Bosnia and Herzegovina", "AO_BALKANS"),
    "mostar": (43.3438, 17.8078, "Bosnia and Herzegovina", "AO_BALKANS"),
    "kosovo": (42.6026, 20.903, "Kosovo", "AO_BALKANS"),
    "pristina": (42.6629, 21.1655, "Kosovo", "AO_BALKANS"),
    "bulgaria": (42.7339, 25.4858, "Bulgaria", "AO_BALKANS"),
    "sofia": (42.6977, 23.3219, "Bulgaria", "AO_BALKANS"),
    "greece": (39.0742, 21.8243, "Greece", "AO_BALKANS"),
    "athens": (37.9838, 23.7275, "Greece", "AO_BALKANS"),
    "thessaloniki": (40.6401, 22.9444, "Greece", "AO_BALKANS"),
    "north macedonia": (41.6086, 21.7453, "North Macedonia", "AO_BALKANS"),
    "skopje": (41.9981, 21.4254, "North Macedonia", "AO_BALKANS"),
    "albania": (41.1533, 20.1683, "Albania", "AO_BALKANS"),
    "tirana": (41.3275, 19.8187, "Albania", "AO_BALKANS"),
    "montenegro": (42.7087, 19.3744, "Montenegro", "AO_BALKANS"),
    "podgorica": (42.4304, 19.2594, "Montenegro", "AO_BALKANS"),

    # AO_LEVANT
    "beirut": (33.8938, 35.5018, "Lebanon", "AO_LEVANT"),
    "lebanon": (33.8547, 35.8623, "Lebanon", "AO_LEVANT"),
    "south lebanon": (33.27, 35.27, "Lebanon", "AO_LEVANT"),
    "litani": (33.3, 35.5, "Lebanon", "AO_LEVANT"),
    "amman": (31.9454, 35.9284, "Jordan", "AO_LEVANT"),
    "jordan": (30.5852, 36.2384, "Jordan", "AO_LEVANT"),
    "irbid": (32.5556, 35.85, "Jordan", "AO_LEVANT"),
    "zaatari": (32.29, 36.32, "Jordan", "AO_LEVANT"),
    "damascus": (33.5138, 36.2765, "Syria", "AO_LEVANT"),
    "syria": (34.8021, 38.9968, "Syria", "AO_LEVANT"),
    "golan": (33.0, 35.75, "Golan Heights", "AO_LEVANT"),
    "israel": (31.0461, 34.8516, "Israel", "AO_LEVANT"),
    "tel aviv": (32.0853, 34.7818, "Israel", "AO_LEVANT"),
    "gaza": (31.5, 34.47, "Gaza", "AO_LEVANT"),
    "west bank": (31.9, 35.2, "West Bank", "AO_LEVANT"),
    "iraq": (33.2232, 43.6793, "Iraq", "AO_LEVANT"),
    "baghdad": (33.3152, 44.3661, "Iraq", "AO_LEVANT"),
    "iran": (32.4279, 53.688, "Iran", "AO_LEVANT"),
    "yemen": (15.5527, 48.5164, "Yemen", "AO_LEVANT"),
    "red sea": (20.0, 38.0, "Red Sea", "AO_LEVANT"),
    "naqoura": (33.1275, 35.1258, "Lebanon (UNIFIL HQ)", "AO_LEVANT"),
    "dahiyeh": (33.85, 35.51, "Lebanon (Beirut southern suburbs)", "AO_LEVANT"),
    "tyre": (33.2733, 35.2036, "Lebanon", "AO_LEVANT"),
    "sidon": (33.5606, 35.3758, "Lebanon", "AO_LEVANT"),
    "nabatieh": (33.3789, 35.4839, "Lebanon", "AO_LEVANT"),
    "irbid": (32.5556, 35.85, "Jordan", "AO_LEVANT"),
    "karak": (31.1853, 35.7047, "Jordan", "AO_LEVANT"),
    "aqaba": (29.5267, 35.0078, "Jordan", "AO_LEVANT"),
    "mafraq": (32.3431, 36.2081, "Jordan", "AO_LEVANT"),
    "haifa": (32.794, 34.9896, "Israel", "AO_LEVANT"),
}

# ---------------------------------------------------------------------------
# Category keywords -> (category label, severity baseline)
# ---------------------------------------------------------------------------
CATEGORY_RULES = [
    # Highest-consequence event types come first.  A report about missiles
    # being intercepted is still a kinetic attack, not merely an incursion.
    (["ied", "car bomb", "suicide bombing", "bombing", "вибух", "взрыв"], "bombing", 5),
    (["air strike", "air strikes", "airstrike", "airstrikes", "drone strike",
      "drone strikes", "drone attack", "drone attacks", "rocket fire",
      "shelling", "missile attack", "missile attacks", "missile strike",
      "missile strikes", "missiles launched", "missile launched",
      "cross-border strike", "удар", "обстрел", "ракет", "дрон"],
     "kinetic_strike", 5),
    (["sabotage", "arson", "explosive device", "cut cable", "cable damage",
      "undersea cable", "pipeline leak", "pipeline damage"], "sabotage", 4),
    (["jamming", "gps spoofing", "gnss interference", "signal interference"],
     "electronic_warfare", 3),
    (["cyberattack", "cyber attack", "cyber incident", "ransomware",
      "malware attack", "denial-of-service", "ddos"], "cyber_attack", 3),
    (["espionage", "spy ring", "expelled diplomat", "intelligence officer arrested"],
     "espionage", 3),
    (["airspace violation", "airspace incursion", "scrambled jets", "qra scramble"],
     "airspace_incursion", 3),
    (["snap exercise", "snap drill", "military drill", "war games", "exercise zapad"],
     "exercise", 2),
    (["protest", "protests", "demonstration", "demonstrations", "riot", "riots"],
     "civil_unrest", 2),
    (["arrest", "arrests", "arrested", "detained", "security raid", "police raid",
      "smuggling", "weapons seizure", "arms seizure", "contraband"],
     "security_operation", 2),
    (["statement", "condemn", "summit", "meeting", "visit"], "diplomatic", 1),
]

DEFAULT_CATEGORY = ("unclassified_reporting", 1)


@dataclass
class Classification:
    ao: Optional[str]
    lat: Optional[float]
    lon: Optional[float]
    country: Optional[str]
    category: str
    severity: int
    is_sigact: bool


def _contains_phrase(text: str, phrase: str) -> bool:
    """Match complete words/phrases, including Unicode scripts.

    Plain substring matching made "riot" match "Patriot" and silently created
    large numbers of false SIGACTs. Whitespace is flexible for RSS HTML text.
    """
    escaped = re.escape(phrase.lower()).replace(r"\ ", r"\s+")
    return re.search(rf"(?<!\w){escaped}(?!\w)", text, flags=re.UNICODE) is not None


def classify(title: str, summary: str, source_ao_hint: Optional[str] = None) -> Classification:
    text = re.sub(r"\s+", " ", f"{title} {summary or ''}".lower()).strip()

    ao, lat, lon, country = None, None, None, None
    # Prefer the most specific matching place ("south lebanon" over
    # "lebanon") so map markers use the best available location.
    for place in sorted(GAZETTEER, key=len, reverse=True):
        p_lat, p_lon, p_country, p_ao = GAZETTEER[place]
        if _contains_phrase(text, place):
            ao, lat, lon, country = p_ao, p_lat, p_lon, p_country
            break

    if ao is None and source_ao_hint in ("AO_HIGH_NORTH", "AO_EUROPE", "AO_BALKANS", "AO_LEVANT"):
        ao = source_ao_hint

    category, severity = DEFAULT_CATEGORY
    for keywords, cat_label, base_severity in CATEGORY_RULES:
        if any(_contains_phrase(text, keyword) for keyword in keywords):
            category, severity = cat_label, base_severity
            break

    # A SIGACT is anything with a named AO and a category more specific than
    # "diplomatic" / "unclassified_reporting" background noise.
    is_sigact = ao is not None and category not in ("diplomatic", "unclassified_reporting")

    return Classification(ao, lat, lon, country, category, severity, is_sigact)
