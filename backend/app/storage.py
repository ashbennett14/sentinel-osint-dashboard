"""Audio object storage with a local-filesystem development fallback."""

from __future__ import annotations

from pathlib import Path
import re
from urllib.parse import quote, urlsplit

import requests

from app.config import settings


R2_PREFIX = "r2--"
AUDIO_CACHE_CONTROL = "public, max-age=604800, immutable"


def r2_audio_ready() -> bool:
    try:
        endpoint = urlsplit(settings.R2_AUDIO_ENDPOINT)
    except ValueError:
        return False
    return bool(
        endpoint.scheme == "https" and endpoint.netloc == endpoint.hostname
        and re.fullmatch(r"[a-f0-9]{32}(?:\.(?:eu|fedramp))?\.r2\.cloudflarestorage\.com", endpoint.hostname or "")
        and not (endpoint.path or endpoint.query or endpoint.fragment)
        and settings.R2_AUDIO_BUCKET and settings.R2_AUDIO_ACCESS_KEY_ID
        and settings.R2_AUDIO_SECRET_ACCESS_KEY
    )


def new_audio_key(filename: str) -> str:
    if settings.R2_AUDIO_ENDPOINT or settings.R2_AUDIO_BUCKET:
        if not r2_audio_ready():
            raise RuntimeError("R2 audio storage is configured but not ready")
        return R2_PREFIX + filename
    return filename


def cloud_storage_enabled(key: str = "") -> bool:
    if key.startswith(R2_PREFIX):
        return r2_audio_ready()
    return bool(
        settings.SUPABASE_URL
        and (
            settings.SUPABASE_SERVICE_ROLE_KEY
            or (settings.SUPABASE_S3_ACCESS_KEY_ID and settings.SUPABASE_S3_SECRET_ACCESS_KEY)
        )
    )


def _r2_client():
    import boto3
    from botocore.config import Config

    return boto3.client(
        "s3", endpoint_url=settings.R2_AUDIO_ENDPOINT, region_name="auto",
        aws_access_key_id=settings.R2_AUDIO_ACCESS_KEY_ID,
        aws_secret_access_key=settings.R2_AUDIO_SECRET_ACCESS_KEY,
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"},
                      request_checksum_calculation="when_required",
                      response_checksum_validation="when_required"),
    )


def _r2_key(key: str, download: bool = False) -> str:
    name = key.removeprefix(R2_PREFIX)
    if not re.fullmatch(r"sentinel-morning-\d{4}-\d{2}-\d{2}-\d{6}\.m4a", name):
        raise ValueError("Invalid R2 episode key")
    return f"downloads/{name}" if download else f"episodes/{name}"


def _s3_enabled() -> bool:
    return bool(
        settings.SUPABASE_S3_ENDPOINT
        and settings.SUPABASE_S3_ACCESS_KEY_ID
        and settings.SUPABASE_S3_SECRET_ACCESS_KEY
    )


def _s3_client():
    import boto3

    return boto3.client(
        "s3",
        endpoint_url=settings.SUPABASE_S3_ENDPOINT,
        region_name=settings.SUPABASE_S3_REGION,
        aws_access_key_id=settings.SUPABASE_S3_ACCESS_KEY_ID,
        aws_secret_access_key=settings.SUPABASE_S3_SECRET_ACCESS_KEY,
    )


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
    if key.startswith(R2_PREFIX):
        if not r2_audio_ready():
            raise RuntimeError("R2 audio storage is unavailable")
        client = _r2_client()
        bucket = settings.R2_AUDIO_BUCKET
        filename = key.removeprefix(R2_PREFIX).rsplit("-", 1)[0] + ".m4a"
        try:
            with path.open("rb") as audio:
                for download in (False, True):
                    audio.seek(0)
                    client.put_object(
                        Bucket=bucket, Key=_r2_key(key, download), Body=audio,
                        ContentType="audio/mp4", CacheControl=AUDIO_CACHE_CONTROL,
                        ContentDisposition=f'attachment; filename="{filename}"' if download else "inline",
                    )
        except Exception:
            for download in (False, True):
                try:
                    client.delete_object(Bucket=bucket, Key=_r2_key(key, download))
                except Exception:
                    pass
            raise
        return
    if not cloud_storage_enabled(key):
        return
    if _s3_enabled():
        with path.open("rb") as audio:
            _s3_client().put_object(
                Bucket=settings.SUPABASE_AUDIO_BUCKET,
                Key=key,
                Body=audio,
                ContentType="audio/mp4",
                CacheControl=AUDIO_CACHE_CONTROL,
            )
        return
    headers = {
        **_service_headers(),
        "Content-Type": "audio/mp4",
        "x-upsert": "true",
        "Cache-Control": "604800",
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
    if key.startswith(R2_PREFIX):
        if not r2_audio_ready():
            raise RuntimeError("R2 audio storage is unavailable")
        client = _r2_client()
        for download in (False, True):
            client.delete_object(Bucket=settings.R2_AUDIO_BUCKET, Key=_r2_key(key, download))
        return
    if not cloud_storage_enabled(key):
        return
    if _s3_enabled():
        _s3_client().delete_object(Bucket=settings.SUPABASE_AUDIO_BUCKET, Key=key)
        return
    headers = _service_headers()
    response = requests.delete(
        f"{settings.SUPABASE_URL}/storage/v1/object/{quote(settings.SUPABASE_AUDIO_BUCKET, safe='')}",
        headers={**headers, "Content-Type": "application/json"},
        json={"prefixes": [key]},
        timeout=30,
    )
    response.raise_for_status()


def audio_location_available(key: str) -> bool:
    if key.startswith(R2_PREFIX):
        return r2_audio_ready()
    return bool(settings.SUPABASE_URL and key)


def public_audio_url(key: str, download: bool = False) -> str | None:
    if key.startswith(R2_PREFIX):
        if not r2_audio_ready():
            return None
        return _r2_client().generate_presigned_url(
            "get_object", Params={"Bucket": settings.R2_AUDIO_BUCKET, "Key": _r2_key(key, download)},
            ExpiresIn=3600,
        )
    return _object_url(key, public=True) if settings.SUPABASE_URL and key else None
