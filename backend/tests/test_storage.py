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


def test_r2_routes_by_key_and_preserves_legacy_archive(monkeypatch, tmp_path: Path):
    audio = tmp_path / "episode.m4a"
    audio.write_bytes(b"audio")
    filename = "sentinel-morning-2026-11-14-070000.m4a"
    client = Mock()
    client.generate_presigned_url.return_value = "https://example.test/signed"
    monkeypatch.setattr(storage.settings, "R2_AUDIO_ENDPOINT", "https://" + "a" * 32 + ".r2.cloudflarestorage.com")
    monkeypatch.setattr(storage.settings, "R2_AUDIO_BUCKET", "sentinel-audio")
    monkeypatch.setattr(storage.settings, "R2_AUDIO_ACCESS_KEY_ID", "key")
    monkeypatch.setattr(storage.settings, "R2_AUDIO_SECRET_ACCESS_KEY", "secret")
    monkeypatch.setattr(storage.settings, "SUPABASE_URL", "https://legacy.supabase.co")
    monkeypatch.setattr(storage, "_r2_client", lambda: client)

    key = storage.new_audio_key(filename)
    storage.upload_audio(audio, key)
    calls = [call.kwargs for call in client.put_object.call_args_list]
    assert [call["Key"] for call in calls] == [f"episodes/{filename}", f"downloads/{filename}"]
    assert calls[0]["ContentDisposition"] == "inline"
    assert calls[1]["ContentDisposition"].startswith("attachment;")
    assert storage.public_audio_url(key, download=True) == "https://example.test/signed"
    assert client.generate_presigned_url.call_args.kwargs["Params"]["Key"] == f"downloads/{filename}"
    assert "legacy.supabase.co" in storage.public_audio_url(filename)
    storage.delete_audio(key)
    assert len(client.delete_object.call_args_list) == 2
    monkeypatch.setattr(storage.settings, "R2_AUDIO_SECRET_ACCESS_KEY", "")
    assert not storage.audio_location_available(key)
    assert storage.public_audio_url(key) is None
    with pytest.raises(RuntimeError, match="not ready"):
        storage.new_audio_key(filename)
