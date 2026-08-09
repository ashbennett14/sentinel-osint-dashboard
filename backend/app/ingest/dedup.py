"""
Groups articles that are almost certainly reporting the same real-world
event into a cluster, so the map/feed can show one SIGACT with multiple
contributing sources instead of five near-identical markers.

Approach (deliberately simple/transparent, not ML): within the same AO +
category, look at articles published within CLUSTER_WINDOW_HOURS of each
other and compare normalized titles with difflib. If similarity clears
SIMILARITY_THRESHOLD, they join the same cluster_key. The earliest article
in a cluster is marked is_cluster_primary — that's the one the map plots
and the brief cites as the representative item, with the rest listed as
"also reported by".
"""
import re
from datetime import timedelta
from difflib import SequenceMatcher

from sqlalchemy.orm import Session

from app.models import Article

CLUSTER_WINDOW_HOURS = 36
SIMILARITY_THRESHOLD = 0.55

_STOPWORDS = {
    "the", "a", "an", "in", "on", "at", "of", "to", "for", "and", "with",
    "over", "amid", "after", "as", "is", "are", "says", "said", "reports",
    "reported", "near",
}


def _normalize(title: str) -> str:
    words = re.findall(r"[a-z0-9]+", title.lower())
    return " ".join(w for w in words if w not in _STOPWORDS)


def assign_cluster(db: Session, article: Article):
    """Call after classify() has set ao/category/published_at on `article`."""
    if not article.ao or not article.is_sigact:
        return  # background noise isn't clustered

    since = article.published_at - timedelta(hours=CLUSTER_WINDOW_HOURS)
    until = article.published_at + timedelta(hours=CLUSTER_WINDOW_HOURS)

    candidates = (
        db.query(Article)
        .filter(
            Article.ao == article.ao,
            Article.category == article.category,
            Article.published_at >= since,
            Article.published_at <= until,
            Article.cluster_key.isnot(None),
            Article.id != article.id,
        )
        .all()
    )

    norm_new = _normalize(article.title)
    best_match, best_ratio = None, 0.0
    for cand in candidates:
        ratio = SequenceMatcher(None, norm_new, _normalize(cand.title)).ratio()
        if ratio > best_ratio:
            best_match, best_ratio = cand, ratio

    if best_match and best_ratio >= SIMILARITY_THRESHOLD:
        article.cluster_key = best_match.cluster_key
        article.is_cluster_primary = False
    else:
        article.cluster_key = f"c{article.id}"
        article.is_cluster_primary = True
