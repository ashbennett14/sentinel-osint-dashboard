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
    assert "Authorization" in post.call_args.kwargs["headers"]


def test_new_secret_key_is_not_sent_as_a_bearer_token(monkeypatch):
    monkeypatch.setattr(storage.settings, "SUPABASE_SERVICE_ROLE_KEY", "sb_secret_example")

    assert storage._service_headers() == {"apikey": "sb_secret_example"}


def test_s3_upload_uses_private_server_credentials(monkeypatch, tmp_path: Path):
    audio = tmp_path / "episode.m4a"
    audio.write_bytes(b"audio")
    client = Mock()
    monkeypatch.setattr(storage.settings, "SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setattr(storage.settings, "SUPABASE_S3_ENDPOINT", "https://example.storage.supabase.co/storage/v1/s3")
    monkeypatch.setattr(storage.settings, "SUPABASE_S3_ACCESS_KEY_ID", "access")
    monkeypatch.setattr(storage.settings, "SUPABASE_S3_SECRET_ACCESS_KEY", "secret")
    monkeypatch.setattr(storage, "_s3_client", Mock(return_value=client))

    storage.upload_audio(audio, "episode.m4a")

    kwargs = client.put_object.call_args.kwargs
    assert kwargs["Bucket"] == "audio-briefs"
    assert kwargs["Key"] == "episode.m4a"
    assert kwargs["ContentType"] == "audio/mp4"


def test_upload_error_includes_supabase_response(monkeypatch, tmp_path: Path):
    audio = tmp_path / "episode.m4a"
    audio.write_bytes(b"audio")
    response = Mock(ok=False, status_code=400, text='{"message":"invalid upload"}')
    monkeypatch.setattr(storage.settings, "SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setattr(storage.settings, "SUPABASE_SERVICE_ROLE_KEY", "secret")
    monkeypatch.setattr(storage.requests, "post", Mock(return_value=response))

    with pytest.raises(requests.HTTPError, match="invalid upload"):
        storage.upload_audio(audio, "episode.m4a")
