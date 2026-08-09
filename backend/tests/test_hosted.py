from fastapi import HTTPException

from app.config import settings
from app.main import require_mutations_enabled
from app.storage import public_audio_url


def test_hosted_mutations_are_forbidden(monkeypatch):
    monkeypatch.setattr(settings, "HOSTED_MODE", True)
    monkeypatch.setattr(settings, "HOSTED_READ_ONLY", True)
    try:
        require_mutations_enabled()
    except HTTPException as exc:
        assert exc.status_code == 403
    else:
        raise AssertionError("hosted mutation guard did not reject the request")


def test_local_mutations_remain_available(monkeypatch):
    monkeypatch.setattr(settings, "HOSTED_MODE", False)
    monkeypatch.setattr(settings, "HOSTED_READ_ONLY", False)
    assert require_mutations_enabled() is None


def test_public_audio_url_does_not_need_service_role_key(monkeypatch):
    monkeypatch.setattr(settings, "SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setattr(settings, "SUPABASE_SERVICE_ROLE_KEY", "")
    monkeypatch.setattr(settings, "SUPABASE_AUDIO_BUCKET", "audio-briefs")
    assert public_audio_url("episode.m4a") == (
        "https://example.supabase.co/storage/v1/object/public/audio-briefs/episode.m4a"
    )
