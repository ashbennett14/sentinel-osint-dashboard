import pytest

from app.analysis.synopsis import _extract_json, _validate_synopsis, WINDOWS


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
