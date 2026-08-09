import logging
import json
from datetime import datetime, timedelta
from typing import Optional, List

from fastapi import BackgroundTasks, FastAPI, Depends, Query, HTTPException, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.ao import VALID_AOS
from app.database import get_db, init_db
from app.models import Article, Source, Synopsis, Brief, AudioBrief, SystemStatus
from app.schemas import (
    SigActOut, SynopsisOut, BriefOut, BriefSummaryOut,
    AudioBriefOut, AudioBriefSummaryOut,
    SourceHealthOut, SourceCreate, SourceUpdate, SystemStatusOut,
)
from app.scheduler import (
    audio_job_running,
    start_scheduler,
    run_audio_brief_job,
    run_synopsis_job,
    run_brief_job,
    run_ingest_cycle,
)
from app.analysis.audio_brief import audio_path_for
from app.storage import public_audio_url

logging.basicConfig(level=settings.LOG_LEVEL)
logger = logging.getLogger("sentinel.main")

app = FastAPI(title="SENTINEL OSINT Fusion Dashboard API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.ALLOWED_ORIGINS) if settings.HOSTED_MODE else ["*"],
    allow_methods=["GET", "HEAD", "OPTIONS"] if settings.HOSTED_MODE else ["*"],
    allow_headers=["Accept", "Content-Type", "Range"] if settings.HOSTED_MODE else ["*"],
)

_scheduler = None


@app.on_event("startup")
def on_startup():
    global _scheduler
    init_db()
    if settings.SCHEDULER_ENABLED and not settings.HOSTED_MODE:
        _scheduler = start_scheduler()


@app.middleware("http")
async def response_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; img-src 'self' data: https:; style-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com https://fonts.googleapis.com; font-src https://fonts.gstatic.com; script-src 'self' https://cdnjs.cloudflare.com; connect-src 'self' https:; media-src 'self' https: blob:; frame-ancestors 'none'",
    )
    if request.method in ("GET", "HEAD") and request.url.path.startswith("/api/"):
        if request.url.path.startswith("/api/audio-brief") or request.url.path == "/api/health":
            # Today's episode is atomically replaced under the same database
            # id. Never cache metadata or the redirect to its revisioned file.
            response.headers["Cache-Control"] = "no-store"
        else:
            response.headers.setdefault(
                "Cache-Control", "public, max-age=60, s-maxage=300, stale-while-revalidate=600"
            )
    return response


def require_mutations_enabled():
    if settings.HOSTED_READ_ONLY or settings.HOSTED_MODE:
        raise HTTPException(status_code=403, detail="This public deployment is read-only")


WINDOW_HOURS = {"24h": 24, "48h": 48, "7d": 24 * 7, "30d": 24 * 30}


@app.get("/api/health")
def health(db: Session = Depends(get_db)):
    statuses = db.query(SystemStatus).all()
    return {
        "status": "ok",
        "time": datetime.utcnow().isoformat(),
        "llm_provider": settings.LLM_PROVIDER,
        "components": [SystemStatusOut.model_validate(s) for s in statuses],
    }


@app.get("/api/runtime-config")
def runtime_config():
    return {"read_only": settings.HOSTED_READ_ONLY or settings.HOSTED_MODE}


def _sigact_to_out(a: Article) -> SigActOut:
    item = SigActOut.model_validate(a)
    item.source_name = a.source.name if a.source else None
    item.reliability = a.source.reliability if a.source else None
    return item


@app.get("/api/sigacts", response_model=list[SigActOut])
def get_sigacts(
    ao: Optional[str] = Query(None, description="AO_HIGH_NORTH | AO_EUROPE | AO_BALKANS | AO_LEVANT"),
    window: str = Query("24h", description="24h | 48h | 7d | 30d"),
    category: Optional[str] = Query(None, description="filter by category"),
    q: Optional[str] = Query(None, description="free-text search over title/summary"),
    db: Session = Depends(get_db),
):
    if window not in WINDOW_HOURS:
        raise HTTPException(400, "window must be one of 24h, 48h, 7d, 30d")
    if ao and ao not in VALID_AOS:
        raise HTTPException(400, "invalid AO")
    since = datetime.utcnow() - timedelta(hours=WINDOW_HOURS[window])

    query = db.query(Article).filter(
        Article.is_sigact == True,           # noqa: E712
        Article.is_cluster_primary == True,  # one marker per real-world event
        Article.published_at >= since,
    )
    if ao:
        query = query.filter(Article.ao == ao)
    if category:
        query = query.filter(Article.category == category)
    if q:
        like = f"%{q.lower()}%"
        query = query.filter(
            (Article.title.ilike(like)) | (Article.summary.ilike(like))
        )

    primaries = query.order_by(Article.published_at.desc()).limit(500).all()

    out = []
    for a in primaries:
        item = _sigact_to_out(a)
        if a.cluster_key:
            others = (
                db.query(Article)
                .filter(Article.cluster_key == a.cluster_key, Article.id != a.id)
                .all()
            )
            item.cluster_size = 1 + len(others)
            item.also_reported_by = [o.source.name for o in others if o.source]
        out.append(item)
    return out


@app.get("/api/synopsis", response_model=SynopsisOut)
def get_synopsis(
    ao: str = Query(..., description="AO_HIGH_NORTH | AO_EUROPE | AO_BALKANS | AO_LEVANT"),
    window: str = Query("24h", description="24h | 48h | 7d | 30d"),
    db: Session = Depends(get_db),
):
    if ao not in VALID_AOS:
        raise HTTPException(400, "invalid AO")
    if window not in WINDOW_HOURS:
        raise HTTPException(400, "invalid synopsis window")
    synopsis = (
        db.query(Synopsis)
        .filter(Synopsis.ao == ao, Synopsis.window == window)
        .order_by(Synopsis.generated_at.desc())
        .first()
    )
    if not synopsis:
        raise HTTPException(404, "No synopsis generated yet for this AO/window — wait for the next cycle.")
    return synopsis


@app.get("/api/brief/latest", response_model=BriefOut)
def get_latest_brief(
    ao: str = Query(..., description="AO_HIGH_NORTH | AO_EUROPE | AO_BALKANS | AO_LEVANT"),
    db: Session = Depends(get_db),
):
    if ao not in VALID_AOS:
        raise HTTPException(400, "invalid AO")
    brief = (
        db.query(Brief)
        .filter(Brief.ao == ao)
        .order_by(Brief.generated_at.desc())
        .first()
    )
    if not brief:
        raise HTTPException(404, "No analyst brief generated yet — wait for the next cycle.")
    return brief


@app.get("/api/briefs", response_model=List[BriefSummaryOut])
def list_briefs(
    ao: str = Query(..., description="AO_HIGH_NORTH | AO_EUROPE | AO_BALKANS | AO_LEVANT"),
    limit: int = Query(30, le=200),
    db: Session = Depends(get_db),
):
    if ao not in VALID_AOS:
        raise HTTPException(400, "invalid AO")
    return (
        db.query(Brief)
        .filter(Brief.ao == ao)
        .order_by(Brief.generated_at.desc())
        .limit(limit)
        .all()
    )


@app.get("/api/briefs/{brief_id}", response_model=BriefOut)
def get_brief(brief_id: int, db: Session = Depends(get_db)):
    brief = db.query(Brief).filter(Brief.id == brief_id).first()
    if not brief:
        raise HTTPException(404, "Brief not found")
    return brief


def _audio_brief_out(episode: AudioBrief) -> AudioBriefOut:
    try:
        chapters = json.loads(episode.chapters_json or "[]")
    except json.JSONDecodeError:
        chapters = []
    return AudioBriefOut(
        id=episode.id,
        episode_date=episode.episode_date,
        generated_at=episode.generated_at,
        period_start=episode.period_start,
        period_end=episode.period_end,
        title=episode.title,
        transcript=episode.transcript,
        chapters=chapters,
        audio_url=(
            f"/api/audio-briefs/{episode.id}/file"
            if public_audio_url(episode.audio_filename or "") or audio_path_for(episode)
            else None
        ),
        mime_type=episode.mime_type,
        duration_seconds=episode.duration_seconds,
        word_count=episode.word_count,
        source_article_count=episode.source_article_count,
        voice_engine=episode.voice_engine,
        status=episode.status,
        last_error=episode.last_error,
    )


@app.get("/api/audio-brief/latest", response_model=AudioBriefOut)
def get_latest_audio_brief(db: Session = Depends(get_db)):
    episode = (
        db.query(AudioBrief)
        .filter(AudioBrief.status == "ready")
        .order_by(AudioBrief.generated_at.desc())
        .first()
    )
    if not episode:
        raise HTTPException(404, "No morning audio briefing has been generated yet.")
    return _audio_brief_out(episode)


@app.get("/api/audio-briefs", response_model=List[AudioBriefSummaryOut])
def list_audio_briefs(limit: int = Query(30, ge=1, le=100), db: Session = Depends(get_db)):
    return (
        db.query(AudioBrief)
        .filter(AudioBrief.status == "ready")
        .order_by(AudioBrief.generated_at.desc())
        .limit(limit)
        .all()
    )


@app.get("/api/audio-briefs/{episode_id}", response_model=AudioBriefOut)
def get_audio_brief(episode_id: int, db: Session = Depends(get_db)):
    episode = db.query(AudioBrief).filter(AudioBrief.id == episode_id).first()
    if not episode or episode.status != "ready":
        raise HTTPException(404, "Audio briefing not found")
    return _audio_brief_out(episode)


@app.get("/api/audio-briefs/{episode_id}/file")
def get_audio_brief_file(
    episode_id: int,
    download: bool = Query(False),
    db: Session = Depends(get_db),
):
    episode = db.query(AudioBrief).filter(AudioBrief.id == episode_id).first()
    if episode and episode.status == "ready":
        cloud_url = public_audio_url(episode.audio_filename or "")
        if cloud_url:
            if download:
                separator = "&" if "?" in cloud_url else "?"
                cloud_url = f"{cloud_url}{separator}download=sentinel-morning-{episode.episode_date}.m4a"
            return RedirectResponse(cloud_url, status_code=307, headers={"Cache-Control": "no-store"})
    path = audio_path_for(episode) if episode and episode.status == "ready" else None
    if not path:
        raise HTTPException(404, "Audio file not found")
    return FileResponse(
        path,
        media_type=episode.mime_type,
        filename=f"sentinel-morning-{episode.episode_date}.m4a",
        content_disposition_type="attachment" if download else "inline",
        headers={"Accept-Ranges": "bytes", "Cache-Control": "private, max-age=3600"},
    )


@app.get("/api/sources", response_model=list[SourceHealthOut])
def list_sources(db: Session = Depends(get_db)):
    return db.query(Source).order_by(Source.error_count.desc()).all()


# Kept as an alias for backwards compatibility with earlier versions of the frontend.
@app.get("/api/sources/health", response_model=list[SourceHealthOut])
def sources_health(db: Session = Depends(get_db)):
    return list_sources(db)


@app.post("/api/sources", response_model=SourceHealthOut, dependencies=[Depends(require_mutations_enabled)])
def create_source(payload: SourceCreate, db: Session = Depends(get_db)):
    existing = db.query(Source).filter(Source.url_or_handle == payload.url_or_handle).first()
    if existing:
        raise HTTPException(409, "A source with that URL/handle already exists")
    source = Source(**payload.model_dump())
    db.add(source)
    db.commit()
    db.refresh(source)
    return source


@app.patch("/api/sources/{source_id}", response_model=SourceHealthOut, dependencies=[Depends(require_mutations_enabled)])
def update_source(source_id: int, payload: SourceUpdate, db: Session = Depends(get_db)):
    source = db.query(Source).filter(Source.id == source_id).first()
    if not source:
        raise HTTPException(404, "Source not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(source, field, value)
    db.commit()
    db.refresh(source)
    return source


@app.delete("/api/sources/{source_id}", dependencies=[Depends(require_mutations_enabled)])
def delete_source(source_id: int, db: Session = Depends(get_db)):
    source = db.query(Source).filter(Source.id == source_id).first()
    if not source:
        raise HTTPException(404, "Source not found")
    db.delete(source)
    db.commit()
    return {"status": "deleted"}


@app.post("/api/trigger/ingest", status_code=status.HTTP_202_ACCEPTED, dependencies=[Depends(require_mutations_enabled)])
def trigger_ingest(background_tasks: BackgroundTasks):
    """Manually kick an ingest+classify cycle without waiting for the scheduler."""
    background_tasks.add_task(run_ingest_cycle)
    return {"status": "triggered"}


@app.post("/api/trigger/synopsis", status_code=status.HTTP_202_ACCEPTED, dependencies=[Depends(require_mutations_enabled)])
def trigger_synopsis(background_tasks: BackgroundTasks):
    background_tasks.add_task(run_synopsis_job)
    return {"status": "triggered"}


@app.post("/api/trigger/brief", status_code=status.HTTP_202_ACCEPTED, dependencies=[Depends(require_mutations_enabled)])
def trigger_brief(background_tasks: BackgroundTasks):
    background_tasks.add_task(run_brief_job)
    return {"status": "triggered"}


@app.post("/api/trigger/audio-brief", status_code=status.HTTP_202_ACCEPTED, dependencies=[Depends(require_mutations_enabled)])
def trigger_audio_brief(background_tasks: BackgroundTasks):
    if audio_job_running():
        raise HTTPException(409, "Morning audio briefing generation is already running")
    background_tasks.add_task(run_audio_brief_job)
    return {"status": "triggered"}
