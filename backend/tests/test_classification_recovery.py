from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import scheduler
from app.database import Base
from app.models import Article


def test_recent_batches_survive_interruption_and_resume(monkeypatch):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)
    now = datetime.utcnow()
    with session() as db:
        for id, age in [(1, 120), (2, 4), (3, 3)]:
            db.add(Article(id=id, title="Naval exercise begins off Norway", url=f"https://example.test/{id}",
                           published_at=now - timedelta(hours=age), processed=False))
        db.commit()
    monkeypatch.setattr(scheduler, "SessionLocal", session)
    monkeypatch.setattr(scheduler, "alerts_enabled", lambda: False)
    result = SimpleNamespace(ao="AO_HIGH_NORTH", lat=61, lon=8, country="Norway",
                             category="exercise", severity=3, is_sigact=True)
    encountered = 0

    def interrupted(*args):
        nonlocal encountered
        encountered += 1
        if encountered == 2:
            raise KeyboardInterrupt
        return result

    monkeypatch.setattr(scheduler, "classify", interrupted)
    with pytest.raises(KeyboardInterrupt):
        scheduler.run_classification_pass(strict=True, batch_size=1)
    with session() as db:
        assert db.get(Article, 2).processed is True
        assert db.get(Article, 1).processed is False
        assert db.get(Article, 3).processed is False

    monkeypatch.setattr(scheduler, "classify", lambda *args: result)
    scheduler.run_classification_pass(strict=True, batch_size=1)
    with session() as db:
        first, second, third = [db.get(Article, id) for id in (1, 2, 3)]
        assert all(row.processed for row in (first, second, third))
        assert second.cluster_key == third.cluster_key
        assert second.is_cluster_primary and not third.is_cluster_primary
        assert first.cluster_key != second.cluster_key
