import pytest
import json
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.analysis.synopsis import (
    _compact_article_block,
    _extract_json,
    _fallback_window_assessment,
    _previous_model_synopses,
    _validate_synopsis,
    generate_ao_synopses,
    WINDOWS,
)
from app.database import Base
from app.models import Synopsis


def _valid_payload():
    return {
        window: {
            "strategic": "Strategic assessment.",
            "operational": "Operational assessment.",
            "tactical": "Tactical assessment.",
        }
        for window in WINDOWS
    }


def test_extract_json_accepts_fenced_output():
    import json

    payload = _valid_payload()
    assert _extract_json(f"```json\n{json.dumps(payload)}\n```") == payload


def test_validate_synopsis_accepts_complete_payload():
    _validate_synopsis(_valid_payload())


def test_validate_synopsis_rejects_empty_section():
    payload = _valid_payload()
    payload["24h"]["operational"] = ""

    with pytest.raises(ValueError, match="24h.operational"):
        _validate_synopsis(payload)


def test_validate_synopsis_rejects_thin_model_output_when_reporting_exists():
    with pytest.raises(ValueError, match="underdeveloped 24h.strategic"):
        _validate_synopsis(_valid_payload(), {"24h": 3})


def test_fallback_synopsis_is_substantive_and_event_specific():
    source = SimpleNamespace(reliability="official")
    articles = [
        SimpleNamespace(
            title="Regional authorities reinforce protection around a transport hub",
            summary="Officials announced additional patrols and access controls after a security incident.",
            category="security_operation",
            country="Estonia",
            severity=4,
            published_at=datetime.utcnow() - timedelta(hours=2),
            source=source,
        ),
        SimpleNamespace(
            title="Military exercise begins near the eastern border",
            summary="The exercise includes air-defence and logistics activity over several days.",
            category="exercise",
            country="Finland",
            severity=3,
            published_at=datetime.utcnow() - timedelta(hours=8),
            source=source,
        ),
    ]

    strategic, operational, tactical = _fallback_window_assessment(articles, "24h", 1)

    assert len(strategic.split()) >= 60
    assert len(operational.split()) >= 60
    assert len(tactical.split()) >= 60
    assert "transport hub" in operational
    combined = " ".join((strategic, operational, tactical)).lower()
    assert "military exercise" in combined
    for prohibited in (
        "event set contains",
        "source mix",
        "distinct developments",
        "severity marker",
        "reporting volume",
    ):
        assert prohibited not in combined


def test_compact_article_block_lists_each_event_once_with_window_membership():
    article = SimpleNamespace(
        id=7,
        title="Baltic maritime patrol identifies suspicious vessel activity",
        summary="Authorities increased monitoring near critical infrastructure.",
        category="security_operation",
        country="Estonia",
        severity=3,
        ao="AO_HIGH_NORTH",
        published_at=datetime.utcnow() - timedelta(hours=8),
        source=SimpleNamespace(reliability="official"),
    )
    block = _compact_article_block({window: [article] for window in WINDOWS})

    assert block.count(article.title) == 1
    assert "windows=24h,48h,7d,30d" in block
    assert "age=8h" in block


def test_generation_retries_invalid_full_response_as_two_window_groups():
    article = SimpleNamespace(
        id=9,
        title="Security forces reinforce protection near a Baltic transport hub",
        summary="Additional patrols and access controls were introduced.",
        category="security_operation",
        country="Estonia",
        severity=4,
        ao="AO_HIGH_NORTH",
        published_at=datetime.utcnow() - timedelta(hours=3),
        source=SimpleNamespace(reliability="official"),
    )
    substantive = " ".join(["Measured analytical judgement"] * 50)

    def payload(windows):
        return json.dumps({
            window: {
                "strategic": substantive,
                "operational": substantive,
                "tactical": substantive,
            }
            for window in windows
        })

    class Db:
        def __init__(self):
            self.rows = []

        def add(self, row):
            self.rows.append(row)

        def commit(self):
            pass

        def refresh(self, _row):
            pass

    db = Db()
    with patch("app.analysis.synopsis._window_articles", return_value=[article]), patch(
        "app.analysis.synopsis.complete",
        side_effect=["{truncated", payload(("24h", "48h")), payload(("7d", "30d"))],
    ) as model, patch("app.analysis.synopsis.time.sleep"):
        rows = generate_ao_synopses(db, "AO_HIGH_NORTH")

    assert len(rows) == 4
    assert model.call_count == 3
    assert model.call_args_list[0].kwargs["thinking_level"] == "low"
    assert model.call_args_list[0].kwargs["max_tokens"] == 7000
    assert model.call_args_list[1].kwargs["max_tokens"] == 4000


def test_previous_model_synopses_ignore_newer_fallback_rows():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    old = datetime.utcnow() - timedelta(hours=2)
    new = datetime.utcnow() - timedelta(hours=1)
    for window in WINDOWS:
        db.add(Synopsis(
            ao="AO_BALKANS",
            window=window,
            strategic="A model-written strategic assessment.",
            operational="A model-written operational assessment.",
            tactical="A model-written tactical assessment.",
            generated_at=old,
        ))
        db.add(Synopsis(
            ao="AO_BALKANS",
            window=window,
            strategic="The available developments do not yet demonstrate a fundamental shift.",
            operational="The available evidence supports a localised assessment.",
            tactical="The current disposition favours continuity.",
            generated_at=new,
        ))
    db.commit()

    selected = _previous_model_synopses(db, "AO_BALKANS")

    assert len(selected) == 4
    assert all(row.generated_at == old for row in selected)
    db.close()
