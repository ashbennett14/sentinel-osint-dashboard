from unittest.mock import patch

import pytest

from app.analysis import gemini_client


class _Response:
    def __init__(self, status_code, data=None, text="", headers=None):
        self.status_code = status_code
        self._data = data or {}
        self.text = text
        self.headers = headers or {}

    def json(self):
        return self._data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def test_daily_quota_switches_to_fallback_model_immediately():
    quota = _Response(
        429,
        text="Quota exceeded: GenerateRequestsPerDayPerProjectPerModel-FreeTier",
    )
    success = _Response(200, data={
        "candidates": [{
            "finishReason": "STOP",
            "content": {"parts": [{"text": "fallback response"}]},
        }],
    })
    with patch.object(gemini_client.settings, "GEMINI_API_KEY", "test-key"), patch.object(
        gemini_client.settings, "GEMINI_MODEL", "primary-model"
    ), patch.object(
        gemini_client.settings, "GEMINI_FALLBACK_MODEL", "fallback-model"
    ), patch("app.analysis.gemini_client.requests.post", side_effect=[quota, success]) as post, patch(
        "app.analysis.gemini_client.time.sleep"
    ) as sleep:
        result = gemini_client.complete("system", "user")

    assert result == "fallback response"
    assert post.call_count == 2
    assert "/primary-model:" in post.call_args_list[0].args[0]
    assert "/fallback-model:" in post.call_args_list[1].args[0]
    sleep.assert_not_called()


def test_incomplete_finish_reason_is_rejected():
    incomplete = _Response(200, data={
        "candidates": [{
            "finishReason": "MAX_TOKENS",
            "content": {"parts": [{"text": "{partial"}]},
        }],
        "usageMetadata": {"promptTokenCount": 100, "candidatesTokenCount": 20},
    })
    with patch.object(gemini_client.settings, "GEMINI_API_KEY", "test-key"), patch.object(
        gemini_client.settings, "GEMINI_MODEL", "primary-model"
    ), patch.object(
        gemini_client.settings, "GEMINI_FALLBACK_MODEL", ""
    ), patch("app.analysis.gemini_client.requests.post", return_value=incomplete):
        with pytest.raises(RuntimeError, match="incomplete"):
            gemini_client.complete("system", "user")
