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
