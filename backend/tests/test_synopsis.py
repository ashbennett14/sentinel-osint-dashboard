import pytest
from datetime import datetime, timedelta
from types import SimpleNamespace

from app.analysis.synopsis import (
    _extract_json,
    _fallback_window_assessment,
    _validate_synopsis,
    WINDOWS,
)


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
