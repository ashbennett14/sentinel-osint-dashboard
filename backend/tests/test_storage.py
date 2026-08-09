from pathlib import Path
from unittest.mock import Mock

import pytest
import requests

from app import storage


def test_upload_uses_standard_post_endpoint(monkeypatch, tmp_path: Path):
    audio = tmp_path / "episode.m4a"
    audio.write_bytes(b"audio")
    response = Mock(ok=True)
    post = Mock(return_value=response)
    monkeypatch.setattr(storage.settings, "SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setattr(storage.settings, "SUPABASE_SERVICE_ROLE_KEY", "secret")
    monkeypatch.setattr(storage.settings, "SUPABASE_AUDIO_BUCKET", "audio-briefs")
    monkeypatch.setattr(storage.requests, "post", post)

    storage.upload_audio(audio, "episode.m4a")

    assert post.call_args.args[0].endswith("/storage/v1/object/audio-briefs/episode.m4a")
    assert post.call_args.kwargs["headers"]["x-upsert"] == "true"


def test_upload_error_includes_supabase_response(monkeypatch, tmp_path: Path):
    audio = tmp_path / "episode.m4a"
    audio.write_bytes(b"audio")
    response = Mock(ok=False, status_code=400, text='{"message":"invalid upload"}')
    monkeypatch.setattr(storage.settings, "SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setattr(storage.settings, "SUPABASE_SERVICE_ROLE_KEY", "secret")
    monkeypatch.setattr(storage.requests, "post", Mock(return_value=response))

    with pytest.raises(requests.HTTPError, match="invalid upload"):
        storage.upload_audio(audio, "episode.m4a")
