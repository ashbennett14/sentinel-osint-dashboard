import pytest

from types import SimpleNamespace

from app.analysis.brief import _confidence_assessment, _validate_brief, REQUIRED_SECTIONS
from app.analysis.brief import _resolve_development_sources, _source_link


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


def test_development_citations_resolve_only_supplied_article_records():
    article = SimpleNamespace(id=42, url="https://example.org/story", source=SimpleNamespace(name="Example News"))
    content = "## 3. KEY DEVELOPMENTS\n- **Border activity:** Details. [[article:42]]\n\n## 4. ASSESSMENT\nAnalysis."
    result = _resolve_development_sources(content, [article])
    assert "Source: [Example News](https://example.org/story)." in result
    assert "[[article:" not in result
    with pytest.raises(ValueError, match="missing or invalid"):
        _resolve_development_sources(content.replace("42", "99"), [article])
    with pytest.raises(ValueError, match="missing or invalid"):
        _resolve_development_sources(content.replace("[[article:42]]", ""), [article])


def test_source_link_rejects_non_web_schemes():
    article = SimpleNamespace(url="javascript:alert(1)", source=SimpleNamespace(name="Example News"))
    assert _source_link(article) == "Source: Example News (link unavailable)."


def test_source_link_names_the_publisher_not_the_monitor():
    article = SimpleNamespace(title="Article headline - Original Publisher",
                              url="https://news.google.com/rss/articles/123",
                              source=SimpleNamespace(name="Regional Watch"))
    assert _source_link(article) == "Source: [Original Publisher](https://news.google.com/rss/articles/123)."


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
