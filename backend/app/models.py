from datetime import datetime

from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Float, Boolean, ForeignKey
)
from sqlalchemy.orm import relationship

from app.database import Base


class Source(Base):
    __tablename__ = "sources"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    kind = Column(String, nullable=False)       # rss | social | github | telegram | twitter
    url_or_handle = Column(String, nullable=False, unique=True)
    ao = Column(String, nullable=False)         # AO_HIGH_NORTH | AO_EUROPE | AO_BALKANS | AO_LEVANT | GLOBAL
    reliability = Column(String, default="unverified")
    # 'official' | 'established_media' | 'regional_specialist' | 'unverified'
    enabled = Column(Boolean, default=True)
    last_fetched_at = Column(DateTime, nullable=True)
    last_error = Column(String, nullable=True)
    error_count = Column(Integer, default=0)

    articles = relationship("Article", back_populates="source")


class Article(Base):
    __tablename__ = "articles"

    id = Column(Integer, primary_key=True)
    source_id = Column(Integer, ForeignKey("sources.id"))
    title = Column(String, nullable=False)
    url = Column(String, nullable=False, unique=True)
    summary = Column(Text, nullable=True)
    published_at = Column(DateTime, nullable=False, index=True)
    fetched_at = Column(DateTime, default=datetime.utcnow)

    # Filled in by the classifier/geotagger
    ao = Column(String, nullable=True, index=True)       # one of the four AOs / unclassified
    category = Column(String, nullable=True)             # e.g. sabotage, jamming, strike, statement
    country = Column(String, nullable=True)
    lat = Column(Float, nullable=True)
    lon = Column(Float, nullable=True)
    severity = Column(Integer, default=1)                # 1 low - 5 high, heuristic
    is_sigact = Column(Boolean, default=False)
    processed = Column(Boolean, default=False)
    # Incremented when classification rules change so existing reporting is
    # automatically re-evaluated instead of remaining permanently stale.
    classifier_version = Column(Integer, default=0)

    # Deduplication: articles reporting the same real-world event share a cluster_key
    cluster_key = Column(String, nullable=True, index=True)
    is_cluster_primary = Column(Boolean, default=False)  # representative article for its cluster

    # Alerting: has a severity>=4 alert already been sent for this article's cluster?
    alerted = Column(Boolean, default=False)

    source = relationship("Source", back_populates="articles")


class Synopsis(Base):
    """Rolling written synopsis for a given AO + timeframe window."""
    __tablename__ = "synopses"

    id = Column(Integer, primary_key=True)
    ao = Column(String, nullable=False)          # one of the four isolated AOs
    window = Column(String, nullable=False)      # '24h' | '48h' | '7d' | '30d'
    strategic = Column(Text, nullable=True)
    operational = Column(Text, nullable=True)
    tactical = Column(Text, nullable=True)
    generated_at = Column(DateTime, default=datetime.utcnow)
    source_article_count = Column(Integer, default=0)


class Brief(Base):
    """Daily analyst brief for one isolated Area of Operation."""
    __tablename__ = "briefs"

    id = Column(Integer, primary_key=True)
    ao = Column(String, nullable=False, index=True)  # one isolated AO
    generated_at = Column(DateTime, default=datetime.utcnow)
    content = Column(Text, nullable=False)        # full markdown brief
    fact_check_notes = Column(Text, nullable=True)  # second-pass self-review, if run
    source_article_count = Column(Integer, default=0)


class AudioBrief(Base):
    """One combined, chaptered morning audio product covering all four AOs."""
    __tablename__ = "audio_briefs"

    id = Column(Integer, primary_key=True)
    episode_date = Column(String, nullable=False, unique=True, index=True)
    generated_at = Column(DateTime, default=datetime.utcnow, index=True)
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)
    title = Column(String, nullable=False)
    transcript = Column(Text, nullable=False)
    chapters_json = Column(Text, nullable=False, default="[]")
    audio_filename = Column(String, nullable=True)
    mime_type = Column(String, nullable=False, default="audio/mp4")
    duration_seconds = Column(Float, nullable=True)
    word_count = Column(Integer, default=0)
    source_article_count = Column(Integer, default=0)
    voice_engine = Column(String, nullable=True)
    status = Column(String, nullable=False, default="ready")
    last_error = Column(Text, nullable=True)


class SystemStatus(Base):
    """Single-row-per-component table tracking last LLM success/failure for the UI health banner."""
    __tablename__ = "system_status"

    id = Column(Integer, primary_key=True)
    component = Column(String, unique=True, nullable=False)  # 'synopsis' | 'brief'
    last_success_at = Column(DateTime, nullable=True)
    last_attempt_at = Column(DateTime, nullable=True)
    last_error = Column(String, nullable=True)
