"""
Dispatches to whichever LLM provider is configured (LLM_PROVIDER=anthropic|gemini
in .env), so synopsis.py and brief.py can call complete() without caring which
backend is actually generating the text.
"""
from app.config import settings


def complete(
    system: str,
    user: str,
    max_tokens: int = 2000,
    *,
    json_schema: dict | None = None,
    thinking_level: str | None = None,
) -> str:
    if settings.LLM_PROVIDER == "gemini":
        from app.analysis.gemini_client import complete as gemini_complete
        return gemini_complete(
            system,
            user,
            max_tokens,
            json_schema=json_schema,
            thinking_level=thinking_level,
        )
    else:
        from app.analysis.claude_client import complete as claude_complete
        return claude_complete(system, user, max_tokens)
