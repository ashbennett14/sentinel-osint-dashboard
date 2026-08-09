import logging
import threading
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import or_

from app.config import settings
from app.database import SessionLocal
from app.models import Source, Article, AudioBrief, SystemStatus
from app.sources import SOURCES, RETIRED_SOURCE_URLS
from app.ingest.rss_ingest import fetch_rss_source
from app.ingest.telegram_ingest import fetch_telegram_source
from app.ingest.twitter_ingest import fetch_twitter_source, twitter_enabled
from app.ingest.geotag import CLASSIFIER_VERSION, classify
from app.ingest.dedup import assign_cluster
from app.ingest.notify import send_alert_email, alerts_enabled, ALERT_SEVERITY_THRESHOLD
from app.analysis.synopsis import generate_all_synopses
from app.analysis.brief import generate_brief
from app.analysis.audio_brief import generate_audio_brief

logger = logging.getLogger("sentinel.scheduler")

FETCHERS = {
    "rss": fetch_rss_source,
    "social": fetch_rss_source,  # public RSS/Atom bridges (Bluesky, Reddit, etc.)
    "github": fetch_rss_source,  # GitHub commit/release Atom feeds
    "telegram": fetch_telegram_source,
    "twitter": fetch_twitter_source,
}

_job_locks = {
    "ingest": threading.Lock(),
    "synopsis": threading.Lock(),
    "brief": threading.Lock(),
    "audio": threading.Lock(),
}


def _record_status(db, component: str, success: bool, error: str = None):
    row = db.query(SystemStatus).filter(SystemStatus.component == component).first()
    if not row:
        row = SystemStatus(component=component)
        db.add(row)
    row.last_attempt_at = datetime.utcnow()
    if success:
        row.last_success_at = datetime.utcnow()
        row.last_error = None
    else:
        row.last_error = (error or "unknown error")[:500]
    db.commit()


def seed_sources():
    db = SessionLocal()
    try:
        canonical_urls = {entry["url_or_handle"] for entry in SOURCES}
        # Retired records are disabled rather than deleted so their historical
        # articles keep a valid source relationship.
        if RETIRED_SOURCE_URLS:
            retired = (
                db.query(Source)
                .filter(
                    Source.url_or_handle.in_(RETIRED_SOURCE_URLS),
                    ~Source.url_or_handle.in_(canonical_urls),
                )
                .all()
            )
            for source in retired:
                source.enabled = False
            if retired:
                logger.info("Disabled %d retired source(s)", len(retired))
            db.commit()

        for entry in SOURCES:
            source = db.query(Source).filter(Source.name == entry["name"]).first()
            if not source:
                source = db.query(Source).filter(
                    Source.url_or_handle == entry["url_or_handle"]
                ).first()
            if source:
                source.name = entry["name"]
                source.kind = entry["kind"]
                source.url_or_handle = entry["url_or_handle"]
                source.ao = entry["ao"]
                source.reliability = entry["reliability"]
            else:
                db.add(Source(**entry))
        db.commit()
    except Exception as exc:  # noqa: BLE001
        logger.error("seed_sources failed: %s", exc)
        db.rollback()
    finally:
        db.close()


def run_ingest_cycle():
    """Fetch all enabled sources then immediately classify new articles."""
    if not _job_locks["ingest"].acquire(blocking=False):
        logger.info("Ingest cycle skipped because one is already running")
        return
    db = SessionLocal()
    total_new = 0
    error = None
    try:
        sources = db.query(Source).filter(Source.enabled == True).all()  # noqa: E712
        for source in sources:
            if source.kind == "twitter" and not twitter_enabled():
                continue
            fetcher = FETCHERS.get(source.kind)
            if not fetcher:
                continue
            try:
                total_new += fetcher(db, source)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Fetcher error for %s: %s", source.name, exc)
        logger.info("Ingest cycle complete: %d new articles", total_new)
    except Exception as exc:  # noqa: BLE001
        logger.error("Ingest cycle failed: %s", exc)
        error = str(exc)
    finally:
        db.close()

    try:
        # Classification runs in its own try/except so an ingest error can't
        # prevent it from running, and vice versa.
        run_classification_pass()
        status_db = SessionLocal()
        try:
            _record_status(status_db, "ingest", success=error is None, error=error)
        finally:
            status_db.close()
    finally:
        _job_locks["ingest"].release()


def run_classification_pass():
    db = SessionLocal()
    try:
        unprocessed = db.query(Article).filter(or_(
            Article.processed == False,  # noqa: E712
            Article.classifier_version.is_(None),
            Article.classifier_version < CLASSIFIER_VERSION,
        )).order_by(Article.published_at.asc()).all()

        # Remove stale clusters before rebuilding them with the new rules.
        for article in unprocessed:
            article.cluster_key = None
            article.is_cluster_primary = False
        db.flush()

        for article in unprocessed:
            try:
                with db.begin_nested():
                    source_ao_hint = article.source.ao if article.source else None
                    result = classify(article.title, article.summary or "", source_ao_hint)
                    article.ao = result.ao
                    article.lat = result.lat
                    article.lon = result.lon
                    article.country = result.country
                    article.category = result.category
                    article.severity = result.severity
                    article.is_sigact = result.is_sigact
                    article.processed = True
                    article.classifier_version = CLASSIFIER_VERSION

                    assign_cluster(db, article)
                    db.flush()

                    if (
                        article.is_sigact
                        and article.severity >= ALERT_SEVERITY_THRESHOLD
                        and article.is_cluster_primary
                        and not article.alerted
                        and alerts_enabled()
                    ):
                        if send_alert_email(article):
                            article.alerted = True
            except Exception as exc:  # noqa: BLE001
                logger.warning("Classification error for article %s: %s", article.id, exc)

        db.commit()
        logger.info("Classification pass complete: %d articles processed", len(unprocessed))
    except Exception as exc:  # noqa: BLE001
        logger.error("Classification pass failed: %s", exc)
    finally:
        db.close()


def run_synopsis_job():
    if not _job_locks["synopsis"].acquire(blocking=False):
        logger.info("Synopsis generation skipped because one is already running")
        return
    db = SessionLocal()
    try:
        generate_all_synopses(db)
        _record_status(db, "synopsis", success=True)
        logger.info("Synopsis generation complete")
    except Exception as exc:  # noqa: BLE001
        logger.warning("Synopsis generation failed: %s", exc)
        _record_status(db, "synopsis", success=False, error=str(exc))
    finally:
        db.close()
        _job_locks["synopsis"].release()


def run_brief_job():
    if not _job_locks["brief"].acquire(blocking=False):
        logger.info("Brief generation skipped because one is already running")
        return
    db = SessionLocal()
    try:
        generate_brief(db)
        _record_status(db, "brief", success=True)
        logger.info("Analyst brief generation complete")
    except Exception as exc:  # noqa: BLE001
        logger.warning("Brief generation failed: %s", exc)
        _record_status(db, "brief", success=False, error=str(exc))
    finally:
        db.close()
        _job_locks["brief"].release()


def audio_job_running() -> bool:
    return _job_locks["audio"].locked()


def run_audio_brief_job():
    if not settings.AUDIO_BRIEF_ENABLED:
        return
    if not _job_locks["audio"].acquire(blocking=False):
        logger.info("Audio briefing generation skipped because one is already running")
        return
    db = SessionLocal()
    try:
        episode = generate_audio_brief(db)
        _record_status(db, "audio", success=True)
        logger.info(
            "Morning audio briefing complete: %s, %.1f seconds",
            episode.episode_date,
            episode.duration_seconds or 0,
        )
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        logger.warning("Audio briefing generation failed: %s", exc)
        now = datetime.utcnow()
        local_date = now.replace(tzinfo=ZoneInfo("UTC")).astimezone(
            ZoneInfo(settings.AUDIO_BRIEF_TIMEZONE)
        ).date().isoformat()
        existing = db.query(AudioBrief).filter(AudioBrief.episode_date == local_date).first()
        if not existing:
            db.add(AudioBrief(
                episode_date=local_date,
                period_start=now - timedelta(hours=24),
                period_end=now,
                title=f"SENTINEL Morning Intelligence Update — {local_date}",
                transcript="",
                chapters_json="[]",
                word_count=0,
                source_article_count=0,
                status="failed",
                last_error=str(exc)[:800],
            ))
            db.commit()
        _record_status(db, "audio", success=False, error=str(exc))
    finally:
        db.close()
        _job_locks["audio"].release()


def start_scheduler() -> BackgroundScheduler:
    seed_sources()

    scheduler = BackgroundScheduler()

    # next_run_time=None means "wait one full interval before first run".
    # We use next_run_time for synopsis/brief so the bootstrap ingest
    # (added below) has time to populate articles before generation runs.
    scheduler.add_job(run_ingest_cycle, "interval",
                      minutes=settings.INGEST_INTERVAL_MINUTES,
                      next_run_time=None, id="ingest")
    scheduler.add_job(run_synopsis_job, "interval",
                      minutes=settings.SYNOPSIS_INTERVAL_MINUTES,
                      next_run_time=None, id="synopsis")
    scheduler.add_job(run_brief_job, "interval",
                      minutes=settings.BRIEF_INTERVAL_MINUTES,
                      next_run_time=None, id="brief")
    if settings.AUDIO_BRIEF_ENABLED:
        scheduler.add_job(
            run_audio_brief_job,
            "cron",
            hour=settings.AUDIO_BRIEF_HOUR,
            minute=settings.AUDIO_BRIEF_MINUTE,
            timezone=settings.AUDIO_BRIEF_TIMEZONE,
            coalesce=True,
            max_instances=1,
            misfire_grace_time=6 * 60 * 60,
            id="audio_brief",
        )

    scheduler.start()

    # Kick off an immediate ingest on startup so the map populates quickly.
    scheduler.add_job(run_ingest_cycle, id="ingest_bootstrap")

    # If the service starts after the morning deadline, create today's missing
    # episode shortly after bootstrap collection completes.
    if settings.AUDIO_BRIEF_ENABLED:
        local_now = datetime.now(ZoneInfo(settings.AUDIO_BRIEF_TIMEZONE))
        deadline = local_now.replace(hour=7, minute=0, second=0, microsecond=0)
        if local_now >= deadline:
            catchup_db = SessionLocal()
            try:
                ready_today = catchup_db.query(AudioBrief).filter(
                    AudioBrief.episode_date == local_now.date().isoformat(),
                    AudioBrief.status == "ready",
                ).first()
            finally:
                catchup_db.close()
            if not ready_today:
                scheduler.add_job(
                    run_audio_brief_job,
                    "date",
                    run_date=datetime.now() + timedelta(minutes=2),
                    id="audio_catchup",
                )

    return scheduler
