"""Read-only reporting comparisons and article evidence, scoped to one AO."""
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.models import Article, SystemStatus
from app.reporting import publisher_name


def utc_iso(value):
    return value.replace(tzinfo=timezone.utc).isoformat() if value else None


def _public_url(value):
    try:
        parsed = urlsplit(value)
        if parsed.scheme in {"http", "https"} and parsed.hostname and not parsed.username and not parsed.password:
            return value
    except ValueError:
        pass
    return None


def _publisher(article):
    name = publisher_name(article)
    return name.strip() or None if name else None


def _event_key(article):
    return ("cluster", article.cluster_key) if article.cluster_key else ("article", article.id)


def compare_reporting(db, ao, now):
    recent_start = now - timedelta(hours=24)
    previous_start = now - timedelta(hours=48)
    base = db.query(Article).filter(Article.ao == ao, Article.processed.is_(True), Article.is_sigact.is_(True))
    current_filter = (Article.published_at >= recent_start, Article.published_at < now)
    current = base.filter(*current_filter).options(joinedload(Article.source)).all()
    current_clusters = select(Article.cluster_key).where(
        Article.ao == ao, Article.processed.is_(True), Article.is_sigact.is_(True),
        Article.cluster_key.is_not(None), *current_filter,
    )
    earlier = base.filter(
        Article.published_at < recent_start, Article.cluster_key.in_(current_clusters)
    ).options(joinedload(Article.source)).all() if current else []
    by_event = defaultdict(list)
    prior_by_event = defaultdict(list)
    for article in current:
        by_event[_event_key(article)].append(article)
    for article in earlier:
        prior_by_event[_event_key(article)].append(article)
    items = []
    for key, articles in by_event.items():
        prior = prior_by_event[key]
        publishers = {name.casefold(): name for a in articles if (name := _publisher(a))}
        prior_names = {name.casefold() for a in prior if (name := _publisher(a))}
        added = sorted((publishers[n] for n in publishers.keys() - prior_names), key=str.casefold) if prior else []
        representative = max(articles, key=lambda a: (a.published_at, a.id))
        items.append({
            "article_id": representative.id,
            "title": representative.title,
            "category": representative.category,
            "country": representative.country,
            "kind": "follow_up" if prior else "new",
            "published_at": utc_iso(representative.published_at),
            "previous_window_count": sum(a.published_at >= previous_start for a in prior),
            "current_window_count": len(articles),
            "added_publishers": added,
            "severity": max(a.severity or 0 for a in articles),
        })
    items.sort(key=lambda item: (
        item["kind"] == "new", bool(item["added_publishers"]), item["severity"],
        item["published_at"], item["article_id"],
    ), reverse=True)
    ingest = db.query(SystemStatus).filter_by(component="ingest").first()
    last_success = ingest.last_success_at if ingest else None
    collection = "unavailable" if last_success is None else "current"
    if last_success is not None and (now - last_success > timedelta(hours=2) or ingest.last_error):
        collection = "stale"
    return {
        "ao": ao,
        "current_period": {"start": utc_iso(recent_start), "end": utc_iso(now)},
        "previous_period": {"start": utc_iso(previous_start), "end": utc_iso(recent_start)},
        "last_collected_at": utc_iso(last_success),
        "collection_state": collection,
        "items": items[:5],
    }


def event_evidence(db, ao, article_id, now):
    base = db.query(Article).filter(
        Article.ao == ao, Article.processed.is_(True), Article.published_at <= now,
    )
    anchor = base.filter(Article.id == article_id, Article.is_sigact.is_(True)).first()
    if anchor is None:
        return None
    members = base.filter(Article.cluster_key == anchor.cluster_key) if anchor.cluster_key else base.filter(Article.id == anchor.id)
    total = members.count()
    articles = members.options(joinedload(Article.source)).order_by(Article.published_at.desc(), Article.id.desc()).limit(20).all()
    return {
        "ao": ao, "article_id": anchor.id, "title": anchor.title, "older_count": max(0, total - len(articles)),
        "articles": [{
            "id": a.id, "title": a.title, "publisher": _publisher(a), "url": _public_url(a.url),
            "published_at": utc_iso(a.published_at), "excerpt": (a.summary or "")[:1000],
        } for a in articles],
    }
