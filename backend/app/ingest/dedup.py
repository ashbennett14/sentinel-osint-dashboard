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
from app.reporting import clean_text, publisher_name

CLUSTER_WINDOW_HOURS = 36
SIMILARITY_THRESHOLD = 0.55

_STOPWORDS = {
    "the", "a", "an", "in", "on", "at", "of", "to", "for", "and", "with",
    "over", "amid", "after", "as", "is", "are", "says", "said", "reports",
    "reported", "near",
}

_WARNING_TERMS = {"warn", "warns", "warned", "warning", "warnings", "threat", "risk"}
_NORWAY_TERMS = {"norway", "norwegian"}
_RUSSIA_TERMS = {"russia", "russian"}


def _same_norway_warning(left, right):
    """High-precision fallback for differently worded coverage of one warning."""
    def signature(headline):
        terms = set(headline.split())
        years = {word for word in terms if re.fullmatch(r"20\d{2}", word)}
        warning = ("sabotage" in terms and terms & _NORWAY_TERMS and terms & _RUSSIA_TERMS
                   and terms & _WARNING_TERMS)
        return warning, years
    a, years_a = signature(left)
    b, years_b = signature(right)
    return bool(a and b and not (years_a and years_b and years_a.isdisjoint(years_b)))


def _normalize(title: str) -> str:
    words = re.findall(r"[^\W_]+", clean_text(title).casefold())
    return " ".join(w for w in words if w not in _STOPWORDS)


def _headline(article: Article) -> str:
    title = clean_text(article.title)
    name = publisher_name(article)
    suffix = f" - {name}" if name else ""
    return _normalize(title[:-len(suffix)] if suffix and title.endswith(suffix) else title)


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

    norm_new = _headline(article)
    best_match, best_ratio = None, 0.0
    for cand in candidates:
        candidate = _headline(cand)
        if not norm_new or not candidate:
            continue
        ratio = SequenceMatcher(None, norm_new, candidate).ratio()
        if (article.category == "sabotage"
                and abs(article.published_at - cand.published_at) <= timedelta(hours=18)
                and _same_norway_warning(norm_new, candidate)):
            ratio = max(ratio, SIMILARITY_THRESHOLD)
        if ratio > best_ratio:
            best_match, best_ratio = cand, ratio

    if best_match and best_ratio >= SIMILARITY_THRESHOLD:
        article.cluster_key = best_match.cluster_key
        article.is_cluster_primary = False
    else:
        article.cluster_key = f"c{article.id}"
        article.is_cluster_primary = True
