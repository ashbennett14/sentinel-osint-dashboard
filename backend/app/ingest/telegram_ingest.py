"""
Scrapes the public, no-login HTML preview Telegram exposes at
https://t.me/s/<channel> for any channel with previews enabled. This is not
the Telegram API — no bot token or login required, but it only sees the
channel's recent public post history, has no media/poll parsing, and
Telegram may rate-limit or occasionally change this page's markup.

For heavier use (many channels, high frequency) consider swapping this for
the official Telegram client API (telethon/pyrogram) with your own API
credentials, which is more robust but requires a one-time login flow.
"""
import logging
from datetime import datetime

import requests
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session

from app.models import Source, Article

logger = logging.getLogger("sentinel.ingest.telegram")

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; SentinelOSINT/1.0)"}


def fetch_telegram_source(db: Session, source: Source) -> int:
    new_count = 0
    channel = source.url_or_handle.lstrip("@")
    url = f"https://t.me/s/{channel}"

    # Always stamp so Sources panel shows a real time rather than "not fetched yet"
    source.last_fetched_at = datetime.utcnow()

    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        messages = soup.select("div.tgme_widget_message")
        for msg in messages:
            data_post = msg.get("data-post")  # e.g. "channelname/1234"
            if not data_post:
                continue
            post_url = f"https://t.me/{data_post}"

            exists = db.query(Article).filter(Article.url == post_url).first()
            if exists:
                continue

            text_el = msg.select_one("div.tgme_widget_message_text")
            text = text_el.get_text(" ", strip=True) if text_el else ""
            if not text:
                continue  # media-only post with no caption, skip for now

            time_el = msg.select_one("time")
            published_at = datetime.utcnow()
            if time_el and time_el.get("datetime"):
                try:
                    published_at = datetime.fromisoformat(
                        time_el["datetime"].replace("Z", "+00:00")
                    ).replace(tzinfo=None)
                except ValueError:
                    pass

            title = text[:120] + ("..." if len(text) > 120 else "")

            try:
                db.add(Article(
                    source_id=source.id,
                    title=title,
                    url=post_url,
                    summary=text,
                    published_at=published_at,
                ))
                db.flush()
                new_count += 1
            except Exception:
                db.rollback()
                source.last_fetched_at = datetime.utcnow()

        source.last_fetched_at = datetime.utcnow()
        source.last_error = None
        source.error_count = 0
        db.commit()

    except Exception as exc:  # noqa: BLE001
        logger.warning("Telegram fetch failed for %s: %s", source.name, exc)
        source.last_error = str(exc)[:500]
        source.error_count = (source.error_count or 0) + 1
        db.commit()

    return new_count
