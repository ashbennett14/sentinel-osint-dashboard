from types import SimpleNamespace

from app.ingest.dedup import _same_norway_warning
from app.ingest.rss_ingest import _entry_url
from app.reporting import source_destination


def test_source_link_uses_explicit_publisher_article_not_homepage_or_unrelated_link():
    redirect = "https://news.google.com/rss/articles/example"
    entry = SimpleNamespace(link=redirect, source={"href": "https://publisher.example/"},
                            links=[{"rel": "alternate", "href": "https://publisher.example/"},
                                   {"rel": "alternate", "href": "https://other.example/story"}])
    assert _entry_url(entry) == redirect
    entry.links.append({"rel": "alternate", "href": "https://publisher.example/story"})
    assert _entry_url(entry) == "https://publisher.example/story"
    assert source_destination(redirect) == "Google News"
    assert source_destination("https://t.me/publisher/42") == "Telegram"


def test_warning_clustering_does_not_merge_attack_or_conflicting_year():
    lead = "norwegian intelligence warns of russian sabotage in 2027"
    assert _same_norway_warning(lead, "norway sees heightened threat of sabotage from russia")
    assert not _same_norway_warning(lead, "norway investigates suspected russian sabotage")
    assert not _same_norway_warning(lead, "norway warned about russian sabotage in 2028")
