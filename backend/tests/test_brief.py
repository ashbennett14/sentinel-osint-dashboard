import pytest

from types import SimpleNamespace

from app.analysis.brief import _confidence_assessment, _validate_brief, REQUIRED_SECTIONS


def _complete_brief(ao="AO_HIGH_NORTH"):
    titles = {
        "AO_HIGH_NORTH": "# AO HIGH NORTH DAILY ANALYST BRIEF",
        "AO_EUROPE": "# AO UKRAINE & EASTERN EUROPE DAILY ANALYST BRIEF",
        "AO_BALKANS": "# AO BALKANS DAILY ANALYST BRIEF",
        "AO_LEVANT": "# AO LEVANT DAILY ANALYST BRIEF",
    }
    title = titles[ao]
    body = " ".join(["Assessment based on current open-source reporting."] * 60)
    return title + "\n" + "\n".join(f"{section}\n{body}" for section in REQUIRED_SECTIONS)


def test_validate_brief_accepts_complete_single_ao_product():
    _validate_brief(_complete_brief(), "AO_HIGH_NORTH")


def test_validate_brief_rejects_cross_ao_reference():
    content = _complete_brief() + "\nAO BALKANS"
    with pytest.raises(ValueError, match="crossed the AO boundary"):
        _validate_brief(content, "AO_HIGH_NORTH")


def test_validate_brief_rejects_truncated_product():
    with pytest.raises(ValueError, match="truncated"):
        _validate_brief("# AO HIGH NORTH DAILY ANALYST BRIEF", "AO_HIGH_NORTH")


def test_validate_brief_rejects_untranslated_cyrillic():
    content = _complete_brief() + "\nРакетна небезпека"
    with pytest.raises(ValueError, match="untranslated"):
        _validate_brief(content, "AO_HIGH_NORTH")


def test_fallback_confidence_explains_basis_without_source_arithmetic():
    articles = [
        SimpleNamespace(source=SimpleNamespace(reliability="official"), country="Finland"),
        SimpleNamespace(source=SimpleNamespace(reliability="established_media"), country=None),
        SimpleNamespace(source=SimpleNamespace(reliability="unverified"), country="Estonia"),
    ]

    assessment = _confidence_assessment(articles)

    assert "Overall confidence" in assessment
    assert "supported by official and established reporting" in assessment
    assert "lacks a precise operational location" in assessment
    assert "official: 1" not in assessment


def test_fallback_confidence_avoids_collection_dashboard_language():
    articles = [
        SimpleNamespace(source=SimpleNamespace(reliability="official"), country="Finland"),
        SimpleNamespace(source=SimpleNamespace(reliability="regional_specialist"), country="Estonia"),
    ]

    assessment = _confidence_assessment(articles).lower()

    for prohibited in ("source mix", "event set", "severity marker", "reporting volume"):
        assert prohibited not in assessment
