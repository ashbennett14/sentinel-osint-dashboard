"""Audio object storage with a local-filesystem development fallback."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import quote

import requests

from app.config import settings


def cloud_storage_enabled() -> bool:
    return bool(settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY)


def _object_url(key: str, public: bool = False) -> str:
    prefix = "object/public" if public else "object"
    bucket = quote(settings.SUPABASE_AUDIO_BUCKET, safe="")
    object_key = quote(key, safe="/")
    return f"{settings.SUPABASE_URL}/storage/v1/{prefix}/{bucket}/{object_key}"


def _service_headers() -> dict[str, str]:
    key = settings.SUPABASE_SERVICE_ROLE_KEY
    headers = {"apikey": key}
    # Legacy service_role keys are JWTs and may be used as bearer tokens. New
    # sb_secret keys are opaque and must only be supplied via `apikey`.
    if not key.startswith("sb_secret_"):
        headers["Authorization"] = f"Bearer {key}"
    return headers


def upload_audio(path: Path, key: str) -> None:
    if not cloud_storage_enabled():
        return
    headers = {
        **_service_headers(),
        "Content-Type": "audio/mp4",
        "x-upsert": "true",
        "Cache-Control": "3600",
    }
    with path.open("rb") as audio:
        # Supabase's standard object-upload endpoint accepts POST. PUT is used
        # by the separate resumable-upload protocol and returns a generic 400
        # when sent to this endpoint.
        response = requests.post(_object_url(key), headers=headers, data=audio, timeout=120)
    if not response.ok:
        raise requests.HTTPError(
            f"Supabase audio upload failed ({response.status_code}): {response.text[:500]}",
            response=response,
        )


def delete_audio(key: str) -> None:
    if not cloud_storage_enabled():
        return
    headers = _service_headers()
    response = requests.delete(
        f"{settings.SUPABASE_URL}/storage/v1/object/{quote(settings.SUPABASE_AUDIO_BUCKET, safe='')}",
        headers={**headers, "Content-Type": "application/json"},
        json={"prefixes": [key]},
        timeout=30,
    )
    response.raise_for_status()


def public_audio_url(key: str) -> str | None:
    return _object_url(key, public=True) if settings.SUPABASE_URL and key else None
