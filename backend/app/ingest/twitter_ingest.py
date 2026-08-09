"""
X/Twitter ingestion via API v2 recent-search, filtered to a single author.
Requires TWITTER_BEARER_TOKEN in the environment (paid API tier as of
2024+). If no token is configured, every source of kind "twitter" is
skipped silently and logged once at startup rather than erroring on every
poll cycle.
"""
import logging
from datetime import datetime, timezone

import requests
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Source, Article

logger = logging.getLogger("sentinel.ingest.twitter")

API_URL = "https://api.twitter.com/2/tweets/search/recent"


def twitter_enabled() -> bool:
    return bool(settings.TWITTER_BEARER_TOKEN)


def fetch_twitter_source(db: Session, source: Source) -> int:
    if not twitter_enabled():
        return 0

    new_count = 0
    handle = source.url_or_handle.lstrip("@")
    headers = {"Authorization": f"Bearer {settings.TWITTER_BEARER_TOKEN}"}
    params = {
        "query": f"from:{handle} -is:retweet",
        "max_results": 25,
        "tweet.fields": "created_at,text",
    }

    try:
        resp = requests.get(API_URL, headers=headers, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        for tweet in data.get("data", []):
            tweet_id = tweet["id"]
            post_url = f"https://twitter.com/{handle}/status/{tweet_id}"

            exists = db.query(Article).filter(Article.url == post_url).first()
            if exists:
                continue

            text = tweet.get("text", "")
            created_at = tweet.get("created_at")
            published_at = (
                datetime.fromisoformat(created_at.replace("Z", "+00:00")).replace(tzinfo=None)
                if created_at else datetime.utcnow()
            )
            title = text[:120] + ("..." if len(text) > 120 else "")

            article = Article(
                source_id=source.id,
                title=title,
                url=post_url,
                summary=text,
                published_at=published_at,
            )
            db.add(article)
            new_count += 1

        source.last_fetched_at = datetime.utcnow()
        source.last_error = None
        source.error_count = 0
        db.commit()

    except Exception as exc:  # noqa: BLE001
        logger.warning("Twitter fetch failed for %s: %s", source.name, exc)
        source.last_error = str(exc)[:500]
        source.error_count = (source.error_count or 0) + 1
        db.commit()

    return new_count
