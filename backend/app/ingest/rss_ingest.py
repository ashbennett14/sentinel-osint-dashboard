import logging
from datetime import datetime, timezone

import feedparser
import requests
from sqlalchemy.orm import Session

from app.models import Source, Article

logger = logging.getLogger("sentinel.ingest.rss")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; SentinelOSINT/2.0; +https://github.com/sentinel-osint)",
    "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*",
}
TIMEOUT = 20


def _entry_datetime(entry) -> datetime:
    for key in ("published_parsed", "updated_parsed"):
        val = getattr(entry, key, None)
        if val:
            try:
                return datetime(*val[:6], tzinfo=timezone.utc).replace(tzinfo=None)
            except Exception:
                pass
    return datetime.utcnow()


def fetch_rss_source(db: Session, source: Source) -> int:
    """Fetch one RSS source, insert new articles, return count of new articles."""
    new_count = 0
    # Always stamp last_fetched_at so Sources panel shows "ok · Xh ago" or
    # "err: ..." rather than "not fetched yet" indefinitely.
    source.last_fetched_at = datetime.utcnow()

    try:
        # Pre-fetch with requests so we can set a timeout and a real
        # User-Agent — many sites block the default feedparser agent or
        # Python's urllib with a 403/429, which feedparser then silently
        # treats as an empty feed.
        resp = requests.get(source.url_or_handle, headers=HEADERS, timeout=TIMEOUT)
        resp.raise_for_status()

        parsed = feedparser.parse(resp.content)

        if parsed.bozo and not parsed.entries:
            raise ValueError(f"Feed parse error: {parsed.bozo_exception}")

        for entry in parsed.entries:
            url = getattr(entry, "link", None)
            if not url:
                continue
            exists = db.query(Article).filter(Article.url == url).first()
            if exists:
                continue

            title = getattr(entry, "title", "(no title)")
            summary = getattr(entry, "summary", "") or getattr(entry, "description", "")
            published_at = _entry_datetime(entry)

            try:
                db.add(Article(
                    source_id=source.id,
                    title=title,
                    url=url,
                    summary=summary,
                    published_at=published_at,
                ))
                db.flush()  # catch constraint violations per-article, not per-batch
                new_count += 1
            except Exception:
                db.rollback()
                # Re-stamp last_fetched_at after rollback since it was part of the session
                source.last_fetched_at = datetime.utcnow()

        source.last_error = None
        source.error_count = 0
        db.commit()

    except Exception as exc:  # noqa: BLE001
        logger.warning("RSS fetch failed for %s: %s", source.name, exc)
        source.last_error = str(exc)[:500]
        source.error_count = (source.error_count or 0) + 1
        db.commit()

    return new_count
