#!/usr/bin/env python3
"""Run one idempotent SENTINEL cloud job from GitHub Actions."""

from __future__ import annotations

import argparse
import logging
import sys
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import delete, text

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.analysis.audio_brief import generate_audio_brief, _cleanup_old_episodes  # noqa: E402
from app.analysis.brief import generate_brief  # noqa: E402
from app.analysis.synopsis import generate_all_synopses  # noqa: E402
from app.config import settings  # noqa: E402
from app.database import SessionLocal, engine, init_db  # noqa: E402
from app.models import Article, AudioBrief, SystemStatus  # noqa: E402
from app.scheduler import (  # noqa: E402
    FETCHERS, _record_status, run_classification_pass, seed_sources, twitter_enabled,
)
from app.models import Source  # noqa: E402

logging.basicConfig(level=settings.LOG_LEVEL)
logger = logging.getLogger("sentinel.cloud")


@contextmanager
def job_lock(name: str):
    if engine.dialect.name != "postgresql":
        yield True
        return
    connection = engine.connect()
    acquired = bool(connection.execute(
        text("SELECT pg_try_advisory_lock(hashtext(:name))"), {"name": f"sentinel:{name}"}
    ).scalar())
    try:
        yield acquired
    finally:
        if acquired:
            connection.execute(
                text("SELECT pg_advisory_unlock(hashtext(:name))"), {"name": f"sentinel:{name}"}
            )
        connection.close()


def run_database_job(name: str, callback) -> bool:
    with job_lock(name) as acquired:
        if not acquired:
            logger.info("%s skipped: another worker holds the database lock", name)
            return False
        callback()
        return True


def run_synopsis() -> None:
    db = SessionLocal()
    try:
        generate_all_synopses(db)
        _record_status(db, "synopsis", True)
    except Exception as exc:
        db.rollback()
        _record_status(db, "synopsis", False, str(exc))
        raise
    finally:
        db.close()


def run_briefs() -> None:
    db = SessionLocal()
    try:
        generate_brief(db)
        _record_status(db, "brief", True)
    except Exception as exc:
        db.rollback()
        _record_status(db, "brief", False, str(exc))
        raise
    finally:
        db.close()


def run_audio(force: bool) -> None:
    local_now = datetime.now(ZoneInfo(settings.AUDIO_BRIEF_TIMEZONE))
    episode_date = local_now.date().isoformat()
    db = SessionLocal()
    try:
        existing = db.query(AudioBrief).filter(
            AudioBrief.episode_date == episode_date, AudioBrief.status == "ready"
        ).first()
        if existing and not force:
            logger.info("Audio episode %s already exists", episode_date)
            return
        episode = generate_audio_brief(db)
        _record_status(db, "audio", True)
        logger.info("Generated episode %s (%.1fs)", episode.episode_date, episode.duration_seconds or 0)
    except Exception as exc:
        db.rollback()
        _record_status(db, "audio", False, str(exc))
        raise
    finally:
        db.close()


def cleanup() -> None:
    db = SessionLocal()
    try:
        cutoff = datetime.utcnow() - timedelta(days=settings.ARTICLE_RETENTION_DAYS)
        removed = db.execute(delete(Article).where(Article.published_at < cutoff)).rowcount
        db.commit()
        _cleanup_old_episodes(db)
        logger.info("Removed %d articles older than %d days", removed or 0, settings.ARTICLE_RETENTION_DAYS)
    finally:
        db.close()


def fetch_shard(index: int, count: int) -> None:
    db = SessionLocal()
    total = 0
    try:
        sources = db.query(Source).filter(Source.enabled == True).order_by(Source.id).all()  # noqa: E712
        for source in sources:
            if source.id % count != index or (source.kind == "twitter" and not twitter_enabled()):
                continue
            fetcher = FETCHERS.get(source.kind)
            if not fetcher:
                continue
            try:
                total += fetcher(db, source)
            except Exception as exc:
                logger.warning("Fetcher error for %s: %s", source.name, exc)
        logger.info("Shard %d/%d collected %d articles", index + 1, count, total)
    finally:
        db.close()


def classify_and_record() -> None:
    try:
        run_classification_pass()
        db = SessionLocal()
        try:
            _record_status(db, "ingest", True)
        finally:
            db.close()
    except Exception as exc:
        db = SessionLocal()
        try:
            _record_status(db, "ingest", False, str(exc))
        finally:
            db.close()
        raise


def scheduled_morning_is_due(force: bool) -> bool:
    if force:
        return True
    local_now = datetime.now(ZoneInfo(settings.AUDIO_BRIEF_TIMEZONE))
    if local_now.hour < 5:
        logger.info(
            "Europe/London time is %s; morning job due=False (before 05:00)",
            local_now.isoformat(),
        )
        return False

    episode_date = local_now.date().isoformat()
    db = SessionLocal()
    try:
        ready_episode_exists = db.query(AudioBrief).filter(
            AudioBrief.episode_date == episode_date,
            AudioBrief.status == "ready",
        ).first() is not None
    finally:
        db.close()

    due = not ready_episode_exists
    logger.info(
        "Europe/London time is %s; ready episode for %s exists=%s; morning job due=%s",
        local_now.isoformat(),
        episode_date,
        ready_episode_exists,
        due,
    )
    return due


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("job", choices=("seed", "collect", "classify", "synopsis", "brief", "morning", "audio", "cleanup"))
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--shard-index", type=int, default=0)
    parser.add_argument("--shard-count", type=int, default=1)
    args = parser.parse_args()
    init_db()
    if args.job == "seed":
        seed_sources()
    elif args.job == "collect":
        if not 0 <= args.shard_index < args.shard_count <= 6:
            parser.error("shard index/count must describe at most six workers")
        run_database_job(
            f"collect:{args.shard_index}",
            lambda: fetch_shard(args.shard_index, args.shard_count),
        )
    elif args.job == "classify":
        run_database_job("classify", classify_and_record)
    elif args.job == "synopsis":
        run_database_job("synopsis", run_synopsis)
    elif args.job == "brief":
        run_database_job("brief", run_briefs)
    elif args.job == "audio":
        run_database_job("audio", lambda: run_audio(args.force))
    elif args.job == "morning" and scheduled_morning_is_due(args.force):
        run_database_job("brief", run_briefs)
        run_database_job("audio", lambda: run_audio(args.force))
    elif args.job == "cleanup":
        run_database_job("cleanup", cleanup)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
