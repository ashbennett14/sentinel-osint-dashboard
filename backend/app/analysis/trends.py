"""
Lightweight trend detection: counts SIGACT clusters per AO/category over a
rolling window, so the analyst brief can note things like "3rd suspected
jamming incident in 10 days" instead of treating every event in isolation.
Deliberately simple (a frequency count, not a statistical anomaly model) —
it's meant to hand the LLM enough structure to reason about patterns
itself, not to make the pattern-call automatically.
"""
from collections import Counter
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models import Article

TREND_WINDOW_DAYS = 14


def category_trend_summary(db: Session, ao: str) -> str:
    since = datetime.utcnow() - timedelta(days=TREND_WINDOW_DAYS)
    rows = (
        db.query(Article.category)
        .filter(
            Article.ao == ao,
            Article.published_at >= since,
            Article.is_sigact == True,          # noqa: E712
            Article.is_cluster_primary == True,
        )
        .all()
    )
    counts = Counter(r[0] for r in rows if r[0])
    if not counts:
        return "(no qualifying SIGACT clusters in the trailing 14 days)"

    lines = [f"- {cat}: {n} distinct event(s) in the last {TREND_WINDOW_DAYS} days"
             for cat, n in counts.most_common()]
    return "\n".join(lines)
