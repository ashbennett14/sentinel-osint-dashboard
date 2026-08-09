import logging

from anthropic import Anthropic

from app.config import settings

logger = logging.getLogger("sentinel.analysis.claude")

_client = None


def get_client() -> Anthropic:
    global _client
    if _client is None:
        if not settings.ANTHROPIC_API_KEY:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not set. Add it to backend/.env to enable "
                "synopsis and analyst brief generation."
            )
        _client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    return _client


def complete(system: str, user: str, max_tokens: int = 2000) -> str:
    client = get_client()
    response = client.messages.create(
        model=settings.CLAUDE_MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    parts = [block.text for block in response.content if block.type == "text"]
    return "\n".join(parts).strip()
