from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, Field


class SigActOut(BaseModel):
    id: int
    title: str
    url: str
    summary: Optional[str] = None
    published_at: datetime
    ao: Optional[str] = None
    category: Optional[str] = None
    country: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    severity: int
    source_name: Optional[str] = None
    reliability: Optional[str] = None
    cluster_size: int = 1
    also_reported_by: List[str] = Field(default_factory=list)

    class Config:
        from_attributes = True


class SynopsisOut(BaseModel):
    ao: str
    window: str
    strategic: Optional[str] = None
    operational: Optional[str] = None
    tactical: Optional[str] = None
    generated_at: datetime
    source_article_count: int

    class Config:
        from_attributes = True


class BriefOut(BaseModel):
    id: int
    ao: str
    generated_at: datetime
    content: str
    fact_check_notes: Optional[str] = None
    source_article_count: int

    class Config:
        from_attributes = True


class BriefSummaryOut(BaseModel):
    id: int
    ao: str
    generated_at: datetime
    source_article_count: int

    class Config:
        from_attributes = True


class AudioChapterOut(BaseModel):
    key: str
    title: str
    start_seconds: float


class AudioBriefOut(BaseModel):
    id: int
    episode_date: str
    generated_at: datetime
    period_start: datetime
    period_end: datetime
    title: str
    transcript: str
    chapters: List[AudioChapterOut] = Field(default_factory=list)
    audio_url: Optional[str] = None
    mime_type: str
    duration_seconds: Optional[float] = None
    word_count: int
    source_article_count: int
    voice_engine: Optional[str] = None
    status: str
    last_error: Optional[str] = None


class AudioBriefSummaryOut(BaseModel):
    id: int
    episode_date: str
    generated_at: datetime
    title: str
    duration_seconds: Optional[float] = None
    source_article_count: int
    status: str

    class Config:
        from_attributes = True


class SourceHealthOut(BaseModel):
    id: int
    name: str
    kind: str
    ao: str
    reliability: str
    enabled: bool
    last_fetched_at: Optional[datetime] = None
    last_error: Optional[str] = None
    error_count: int

    class Config:
        from_attributes = True


class SourceCreate(BaseModel):
    name: str
    kind: str            # rss | social | github | telegram | twitter
    url_or_handle: str
    ao: str               # AO_HIGH_NORTH | AO_EUROPE | AO_BALKANS | AO_LEVANT | GLOBAL
    reliability: str = "unverified"


class SourceUpdate(BaseModel):
    enabled: Optional[bool] = None
    reliability: Optional[str] = None
    ao: Optional[str] = None


class SystemStatusOut(BaseModel):
    component: str
    last_success_at: Optional[datetime] = None
    last_attempt_at: Optional[datetime] = None
    last_error: Optional[str] = None

    class Config:
        from_attributes = True
