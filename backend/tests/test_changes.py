from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.changes import compare_reporting, event_evidence
from app.database import Base, get_db
from app.main import app
from app.models import Article, Source, SystemStatus


NOW = datetime(2026, 10, 25, 12)
AO = "AO_BALKANS"


@pytest.fixture
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add_all([Source(id=i, name=name, url_or_handle=f"https://example.test/{i}", kind="rss", ao=AO)
                         for i, name in enumerate(("One", "Two", " one "), 1)])
        session.commit()
        yield session
    engine.dispose()


def article(db, id, hours, *, cluster=None, ao=AO, source=1, url=None):
    db.add(Article(id=id, title=f"Article {id}", url=url or f"https://example.test/articles/{id}",
                   ao=ao, processed=True, is_sigact=True, source_id=source, cluster_key=cluster,
                   published_at=NOW - timedelta(hours=hours)))


def test_comparison_boundaries_followups_dedup_and_ao(db):
    article(db, 1, 24, cluster="new")
    article(db, 2, 12, cluster="new", ao="AO_LEVANT")
    article(db, 3, 48, cluster="follow")
    article(db, 4, 10, cluster="follow", source=2)
    article(db, 5, 2, cluster="follow", source=3)
    article(db, 6, 72, cluster="older")
    article(db, 7, 3, cluster="older")
    article(db, 8, 0)
    article(db, 9, 4)
    article(db, 10, -1)
    db.add(SystemStatus(component="ingest", last_success_at=NOW - timedelta(minutes=15)))
    db.commit()
    result = compare_reporting(db, AO, NOW)
    assert result["collection_state"] == "current"
    assert [i["article_id"] for i in result["items"]] == [9, 1, 5, 7]
    follow = result["items"][2]
    assert (follow["kind"], follow["current_window_count"], follow["previous_window_count"], follow["added_publishers"]) == ("follow_up", 2, 1, ["Two"])
    assert result["items"][3]["kind"] == "follow_up"
    assert result["items"][3]["previous_window_count"] == 0
    start = datetime.fromisoformat(result["current_period"]["start"])
    end = datetime.fromisoformat(result["current_period"]["end"])
    assert result["previous_period"]["end"] == result["current_period"]["start"]
    assert end - start == timedelta(hours=24)
    assert start.astimezone(ZoneInfo("Europe/London")).hour == 13
    assert end.astimezone(ZoneInfo("Europe/London")).hour == 12


def test_stale_unavailable_and_quiet_are_distinct(db):
    assert compare_reporting(db, AO, NOW)["collection_state"] == "unavailable"
    ingest = SystemStatus(component="ingest", last_success_at=NOW - timedelta(hours=3))
    db.add(ingest)
    db.commit()
    assert compare_reporting(db, AO, NOW)["collection_state"] == "stale"
    ingest.last_success_at = NOW
    db.commit()
    result = compare_reporting(db, AO, NOW)
    assert result["collection_state"] == "current" and not result["items"]


def test_reporting_groups_followups_even_when_primary_is_outside_window(db):
    now = datetime.utcnow()
    for id, ao, hours, primary, title in [
        (81, AO, 30, True, "Original article"),
        (82, AO, 2, False, "Follow-up &amp; analysis - Actual Publisher"),
        (83, AO, 3, False, "Earlier follow-up"),
        (84, "AO_LEVANT", 1, True, "Unrelated region"),
        (85, AO, -1, True, "Future timestamp"),
    ]:
        db.add(Article(id=id, ao=ao, source_id=1, title=title, cluster_key="shared",
                       url=f"https://news.google.com/rss/articles/{id}",
                       summary="<p>Some &amp;nbsp; text</p>", published_at=now - timedelta(hours=hours),
                       is_sigact=True, processed=True, is_cluster_primary=primary, severity=2))
    db.commit()
    app.dependency_overrides[get_db] = lambda: db
    try:
        client = TestClient(app)
        response = client.get("/api/sigacts", params={"ao": AO, "window": "24h"})
        assert response.status_code == 200
        [item] = response.json()
        assert item["id"] == 82
        assert item["cluster_size"] == 3
        assert item["source_name"] == "Actual Publisher"
        assert item["summary"] == "Some text"
        evidence = client.get("/api/events/82/evidence", params={"ao": AO}).json()
        assert [a["id"] for a in evidence["articles"]] == [82, 83, 81]
        assert evidence["articles"][0]["publisher"] == "Actual Publisher"
        [wide] = client.get("/api/sigacts", params={"ao": AO, "window": "48h"}).json()
        assert wide["id"] == 81
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_paginated_reporting_totals_and_snapshot(db):
    now = datetime.utcnow()
    for id, hours, severity, mapped in [(91, 1, 4, True), (92, 2, 2, False), (93, 3, 5, True)]:
        db.add(Article(id=id, ao=AO, source_id=1, title=f"Review item {id}",
                       url=f"https://example.test/article/{id}", published_at=now - timedelta(hours=hours),
                       fetched_at=now - timedelta(minutes=5), is_sigact=True, processed=True,
                       severity=severity, lat=42 if mapped else None, lon=20 if mapped else None))
    db.commit()
    app.dependency_overrides[get_db] = lambda: db
    try:
        client = TestClient(app)
        first = client.get("/api/reporting", params={"ao": AO, "limit": 2}).json()
        assert [item["id"] for item in first["items"]] == [91, 92]
        assert (first["total"], first["high"], first["mapped"], first["next_offset"]) == (3, 2, 2, 2)
        db.add(Article(id=94, ao=AO, source_id=1, title="Late arrival",
                       url="https://example.test/article/94", published_at=now - timedelta(minutes=30),
                       fetched_at=datetime.utcnow(), is_sigact=True, processed=True, severity=2))
        db.commit()
        second = client.get("/api/reporting", params={
            "ao": AO, "limit": 2, "offset": first["next_offset"], "as_of": first["as_of"],
        }).json()
        assert [item["id"] for item in second["items"]] == [93]
        assert (second["total"], second["next_offset"]) == (3, None)
        filtered = client.get("/api/reporting", params={"ao": AO, "q": "item 92"}).json()
        assert filtered["total"] == 1
        assert client.get("/api/reporting", params={"ao": AO, "as_of": "2000-01-01T00:00Z"}).status_code == 400
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_collection_health_distinguishes_run_and_feed_failures(db):
    now = datetime.utcnow()
    feed = db.get(Source, 1)
    feed.enabled = True
    feed.last_error = "Network failure"
    ingest = SystemStatus(component="ingest", last_success_at=now - timedelta(hours=3),
                          last_attempt_at=now - timedelta(hours=3))
    db.add(ingest)
    db.commit()
    app.dependency_overrides[get_db] = lambda: db
    try:
        client = TestClient(app)
        get = lambda: client.get("/api/health").json()["collection"]
        assert get()["state"] == "overdue"
        heartbeat = SystemStatus(component="ingest-start", last_success_at=now - timedelta(minutes=10))
        db.add(heartbeat)
        db.commit()
        assert get()["state"] == "running"
        ingest.last_attempt_at = now
        ingest.last_error = "Worker failed"
        db.commit()
        assert get()["state"] == "failed"
        ingest.last_success_at = now
        ingest.last_error = None
        db.commit()
        assert get()["state"] == "current" and get()["failed_feeds"] == 1
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_source_coverage_counts_located_and_unlocated_recent_ao_articles(db):
    now = datetime.utcnow()
    rows = [
        (1, AO, 1, "Kosovo", 1, True),
        (2, AO, 2, None, 1, True),
        (3, "AO_LEVANT", 1, "Jordan", 1, True),
        (4, AO, 1, "Serbia", 169, True),
        (5, AO, 1, "Serbia", 1, False),
        (6, AO, 1, "Albania", -1, True),
    ]
    for id, ao, source, country, hours, sigact in rows:
        db.add(Article(id=id, ao=ao, source_id=source, country=country,
                       title=f"Article {id}", url=f"https://example.test/articles/{id}",
                       processed=True, is_sigact=sigact, published_at=now - timedelta(hours=hours)))
    db.commit()
    app.dependency_overrides[get_db] = lambda: db
    try:
        client = TestClient(app)
        response = client.get("/api/source-coverage", params={"ao": AO})
        assert response.status_code == 200
        data = response.json()
        assert data["by_source"] == {"1": 1, "2": 1}
        assert data["by_country"] == {"Kosovo": 1, "Unlocated": 1}
        assert datetime.fromisoformat(data["end"]) - datetime.fromisoformat(data["start"]) == timedelta(days=7)
        assert client.get("/api/source-coverage", params={"ao": "invalid"}).status_code == 400
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_evidence_limit_safe_links_and_missing_anchor(db):
    for id in range(1, 24):
        article(db, id, id, cluster="shared", url="javascript:alert(1)" if id == 1 else None)
    article(db, 24, 2, cluster="shared", ao="AO_LEVANT")
    article(db, 25, 2)
    db.commit()
    data = event_evidence(db, AO, 1, NOW)
    assert [a["id"] for a in data["articles"]] == list(range(1, 21))
    assert data["older_count"] == 3 and data["articles"][0]["url"] is None
    assert len(event_evidence(db, AO, 25, NOW)["articles"]) == 1
    assert event_evidence(db, AO, 24, NOW) is None
    assert event_evidence(db, AO, 999, NOW) is None


def test_endpoint_validation(db):
    app.dependency_overrides[get_db] = lambda: db
    try:
        client = TestClient(app)
        assert client.get("/api/changes", params={"ao": AO}).json()["ao"] == AO
        assert client.get("/api/changes", params={"ao": "unknown"}).status_code == 400
        assert client.get("/api/events/999/evidence", params={"ao": AO}).status_code == 404
    finally:
        del app.dependency_overrides[get_db]
