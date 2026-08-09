from collections import Counter

from app.ao import VALID_AOS
from app.sources import SOURCES


def test_source_catalogue_has_unique_names_and_urls():
    assert len(SOURCES) == len({source["name"] for source in SOURCES})
    assert len(SOURCES) == len({source["url_or_handle"] for source in SOURCES})


def test_source_catalogue_uses_valid_aos_and_reliability_tiers():
    valid_reliability = {
        "official",
        "established_media",
        "regional_specialist",
        "unverified",
    }
    for source in SOURCES:
        assert source["ao"] in {*VALID_AOS, "GLOBAL"}
        assert source["reliability"] in valid_reliability


def test_balkans_has_substantive_dedicated_coverage():
    counts = Counter(source["ao"] for source in SOURCES)
    assert counts["AO_BALKANS"] >= 50

    balkans = [source for source in SOURCES if source["ao"] == "AO_BALKANS"]
    assert sum(source["reliability"] == "official" for source in balkans) >= 12
    assert sum(source["reliability"] == "established_media" for source in balkans) >= 8
    assert sum(source["reliability"] == "regional_specialist" for source in balkans) >= 8
