import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    HOSTED_MODE: bool = os.getenv("HOSTED_MODE", "false").lower() == "true"
    HOSTED_READ_ONLY: bool = os.getenv("HOSTED_READ_ONLY", "false").lower() == "true"
    SCHEDULER_ENABLED: bool = os.getenv("SCHEDULER_ENABLED", "true").lower() == "true"
    ALLOWED_ORIGINS: tuple[str, ...] = tuple(
        origin.strip() for origin in os.getenv("ALLOWED_ORIGINS", "").split(",") if origin.strip()
    )
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "anthropic")  # "anthropic" | "gemini"

    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    CLAUDE_MODEL: str = os.getenv("CLAUDE_MODEL", "claude-sonnet-5")

    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-flash-latest")
    ENABLE_FACT_CHECK: bool = os.getenv("ENABLE_FACT_CHECK", "true").lower() == "true"

    TWITTER_BEARER_TOKEN: str = os.getenv("TWITTER_BEARER_TOKEN", "")

    # Optional email alerting for severity>=4 SIGACTs — all optional, alerts
    # are simply disabled if ALERT_SMTP_HOST or ALERT_EMAIL_TO are empty.
    ALERT_SMTP_HOST: str = os.getenv("ALERT_SMTP_HOST", "")
    ALERT_SMTP_PORT: int = int(os.getenv("ALERT_SMTP_PORT", "587"))
    ALERT_SMTP_USER: str = os.getenv("ALERT_SMTP_USER", "")
    ALERT_SMTP_PASS: str = os.getenv("ALERT_SMTP_PASS", "")
    ALERT_EMAIL_FROM: str = os.getenv("ALERT_EMAIL_FROM", "")
    ALERT_EMAIL_TO: str = os.getenv("ALERT_EMAIL_TO", "")
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./sentinel.db")
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "").rstrip("/")
    SUPABASE_SERVICE_ROLE_KEY: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    SUPABASE_AUDIO_BUCKET: str = os.getenv("SUPABASE_AUDIO_BUCKET", "audio-briefs")
    SUPABASE_S3_ENDPOINT: str = os.getenv("SUPABASE_S3_ENDPOINT", "").rstrip("/")
    SUPABASE_S3_REGION: str = os.getenv("SUPABASE_S3_REGION", "eu-west-1")
    SUPABASE_S3_ACCESS_KEY_ID: str = os.getenv("SUPABASE_S3_ACCESS_KEY_ID", "")
    SUPABASE_S3_SECRET_ACCESS_KEY: str = os.getenv("SUPABASE_S3_SECRET_ACCESS_KEY", "")
    INGEST_INTERVAL_MINUTES: int = int(os.getenv("INGEST_INTERVAL_MINUTES", "15"))
    # Call budget per day on a free Gemini key:
    #   Synopsis: 3 calls/cycle (1 per AO). At 60min default = 72 calls/day.
    #   Brief: 6-9 calls/cycle (draft + review + occasional revision per AO).
    #   If you're on a key with a very low
    #   RPD cap (20/day), raise these or set ENABLE_FACT_CHECK=false in .env.
    #   The gemini-flash-latest alias (resolves to gemini-3.6-flash as of Aug
    #   2026) has a much higher RPD than the deprecated 2.5-flash model.
    SYNOPSIS_INTERVAL_MINUTES: int = int(os.getenv("SYNOPSIS_INTERVAL_MINUTES", "60"))
    BRIEF_INTERVAL_MINUTES: int = int(os.getenv("BRIEF_INTERVAL_MINUTES", "120"))
    AUDIO_BRIEF_ENABLED: bool = os.getenv("AUDIO_BRIEF_ENABLED", "true").lower() == "true"
    AUDIO_BRIEF_TIMEZONE: str = os.getenv("AUDIO_BRIEF_TIMEZONE", "Europe/London")
    AUDIO_BRIEF_HOUR: int = int(os.getenv("AUDIO_BRIEF_HOUR", "6"))
    AUDIO_BRIEF_MINUTE: int = int(os.getenv("AUDIO_BRIEF_MINUTE", "45"))
    AUDIO_BRIEF_RETENTION_DAYS: int = int(os.getenv("AUDIO_BRIEF_RETENTION_DAYS", "30"))
    AUDIO_BRIEF_VOICE: str = os.getenv("AUDIO_BRIEF_VOICE", "bm_george")
    AUDIO_BRIEF_FALLBACK_VOICE: str = os.getenv("AUDIO_BRIEF_FALLBACK_VOICE", "Daniel")
    AUDIO_BRIEF_SPEED: float = float(os.getenv("AUDIO_BRIEF_SPEED", "1.08"))
    AUDIO_BRIEF_FALLBACK_RATE: int = int(os.getenv("AUDIO_BRIEF_FALLBACK_RATE", "175"))
    KOKORO_MODEL_PATH: str = os.getenv("KOKORO_MODEL_PATH", "")
    KOKORO_VOICES_PATH: str = os.getenv("KOKORO_VOICES_PATH", "")
    ARTICLE_RETENTION_DAYS: int = int(os.getenv("ARTICLE_RETENTION_DAYS", "45"))
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")


settings = Settings()
