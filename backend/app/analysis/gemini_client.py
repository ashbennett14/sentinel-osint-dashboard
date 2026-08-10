"""
Thin wrapper around Google's Gemini API using plain HTTP (via `requests`,
already a dependency) rather than the google-generativeai SDK — one less
package to install/version-match. Matches the same complete(system, user,
max_tokens) -> str signature as claude_client so the rest of the app
doesn't care which provider is active.
"""
import logging
import time

import requests

from app.config import settings

logger = logging.getLogger("sentinel.analysis.gemini")

BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"


def complete(
    system: str,
    user: str,
    max_tokens: int = 2000,
    *,
    json_schema: dict | None = None,
    thinking_level: str | None = None,
) -> str:
    if not settings.GEMINI_API_KEY:
        raise RuntimeError(
            "GEMINI_API_KEY is not set. Add it to backend/.env to enable "
            "synopsis and analyst brief generation."
        )

    url = f"{BASE_URL}/{settings.GEMINI_MODEL}:generateContent"
    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": settings.GEMINI_API_KEY,
    }
    generation_config = {"maxOutputTokens": max_tokens}
    if thinking_level:
        generation_config["thinkingConfig"] = {"thinkingLevel": thinking_level}
    if json_schema:
        # Gemini structured output guarantees syntactically valid JSON and
        # constrains the response to the shape the synopsis parser expects.
        generation_config.update({
            "responseMimeType": "application/json",
            "responseSchema": json_schema,
        })

    payload = {
        "system_instruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": user}]}],
        "generationConfig": generation_config,
    }

    resp = None
    for attempt in range(4):
        resp = requests.post(url, headers=headers, json=payload, timeout=120)
        if resp.status_code not in (429, 503):
            break
        if attempt == 3:
            break
        retry_after = resp.headers.get("Retry-After")
        try:
            delay = float(retry_after) if retry_after else 10.0 * (attempt + 1)
        except ValueError:
            delay = 10.0 * (attempt + 1)
        logger.warning(
            "Gemini returned %s; retrying in %.1fs", resp.status_code, delay
        )
        time.sleep(min(delay, 30.0))
    resp.raise_for_status()
    data = resp.json()

    try:
        candidate = data["candidates"][0]
        parts = candidate["content"]["parts"]
        text = "".join(p.get("text", "") for p in parts).strip()
        finish_reason = candidate.get("finishReason", "STOP")
        if finish_reason != "STOP":
            usage = data.get("usageMetadata", {})
            logger.warning(
                "Gemini stopped with finishReason=%s (prompt=%s, output=%s, chars=%d)",
                finish_reason,
                usage.get("promptTokenCount", "unknown"),
                usage.get("candidatesTokenCount", "unknown"),
                len(text),
            )
            raise RuntimeError(f"Gemini response was incomplete: {finish_reason}")
        return text
    except (KeyError, IndexError) as exc:
        logger.warning("Unexpected Gemini response shape: %s", data)
        raise RuntimeError(f"Could not parse Gemini response: {exc}") from exc
