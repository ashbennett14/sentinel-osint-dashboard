import json
import html
import logging
import re
import time
from collections import Counter
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models import Article, Synopsis
from app.analysis.llm_client import complete

logger = logging.getLogger("sentinel.analysis.synopsis")

WINDOWS = {"24h": 1, "48h": 2, "7d": 7, "30d": 30}

AO_LABELS = {
    "AO_HIGH_NORTH": "AO HIGH NORTH (High North / Finland / Baltic states) — hybrid, grey-zone and regional security activity",
    "AO_EUROPE": "AO UKRAINE & EASTERN EUROPE (Ukraine / eastern and central Europe) — conflict, regional security and spillover activity",
    "AO_BALKANS": "AO BALKANS — military posture, political-security instability, border security, NATO/EU missions and malign influence",
    "AO_LEVANT": "AO LEVANT (Broader Middle East, focus Lebanon/Jordan)",
}

SYSTEM_PROMPT = """You are a military intelligence analyst producing open-source \
intelligence (OSINT) situational synopses for a fusion cell, at four rolling \
timeframes: 24h, 48h, 7d, and 30d. Write in formal, precise military-intelligence \
house style. Each source line is tagged with a reliability tier — official, \
established_media, regional_specialist, or unverified — weight your confidence \
language accordingly. Base every claim ONLY on the source reporting provided — \
never invent events, figures, or attributions not in the source material.

YOU MUST respond with ONLY a raw JSON object — no markdown fences, no ```json, \
no preamble, no explanation, no text before or after the JSON. The response must \
start with { and end with }.

The JSON must have exactly these four top-level keys: "24h", "48h", "7d", "30d". \
Each value is an object with exactly these keys: "strategic", "operational", \
"tactical". For a window containing reporting, each field must be a substantive \
paragraph of 70-130 words and must be specific to that timeframe. Strategic must \
explain the aggregate significance and trajectory; operational must describe the \
geographic and functional operating picture; tactical must prioritise concrete \
developments and near-term implications. Do not recycle identical wording across \
the four windows. If a window is genuinely empty, state "No material change" and \
briefly explain what remains unchanged without padding or invention."""

SECTION_SCHEMA = {
    "type": "object",
    "properties": {
        "strategic": {"type": "string"},
        "operational": {"type": "string"},
        "tactical": {"type": "string"},
    },
    "required": ["strategic", "operational", "tactical"],
}

SYNOPSIS_SCHEMA = {
    "type": "object",
    "properties": {window: SECTION_SCHEMA for window in WINDOWS},
    "required": list(WINDOWS),
}


def _extract_json(raw: str) -> dict:
    """
    Robustly extract the JSON object from a response that may be wrapped in
    markdown code fences, have leading/trailing text, or have other noise.
    Tries three strategies in order:
      1. Direct parse (model obeyed the instruction)
      2. Strip any ``` fences with a regex, then parse
      3. Find the first { and last } and parse whatever is between them
    """
    # Strategy 1: direct
    try:
        return json.loads(raw)
    except Exception:
        pass

    # Strategy 2: strip markdown fences
    stripped = re.sub(r"```(?:json)?\s*", "", raw).strip()
    try:
        return json.loads(stripped)
    except Exception:
        pass

    # Strategy 3: extract outermost {...}
    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(raw[start:end + 1])
        except Exception:
            pass

    return {}


def _window_articles(db: Session, ao: str, days: float):
    since = datetime.utcnow() - timedelta(days=days)
    return (
        db.query(Article)
        .filter(
            Article.ao == ao,
            Article.published_at >= since,
            Article.is_sigact == True,          # noqa: E712
            Article.is_cluster_primary == True,
        )
        .order_by(Article.severity.desc(), Article.published_at.desc())
        .limit(100)
        .all()
    )


def _format_articles(articles) -> str:
    lines = []
    for a in articles:
        reliability = a.source.reliability if a.source else "unverified"
        lines.append(
            f"- [{a.published_at.isoformat()}Z] ({a.category}, sev {a.severity}, "
            f"reliability={reliability}) {a.title} — {(a.summary or '')[:280]}"
        )
    return "\n".join(lines) if lines else "(no qualifying reporting in this window)"


def _validate_synopsis(parsed: dict, window_counts: dict[str, int] | None = None) -> None:
    """Reject incomplete model output instead of persisting empty placeholders."""
    if not isinstance(parsed, dict):
        raise ValueError("Synopsis response was not a JSON object")
    for window in WINDOWS:
        section = parsed.get(window)
        if not isinstance(section, dict):
            raise ValueError(f"Synopsis response is missing the {window} section")
        for field in ("strategic", "operational", "tactical"):
            if not isinstance(section.get(field), str) or not section[field].strip():
                raise ValueError(
                    f"Synopsis response has an empty {window}.{field} section"
                )
            if window_counts and window_counts.get(window, 0) and len(section[field].split()) < 45:
                raise ValueError(
                    f"Synopsis response has an underdeveloped {window}.{field} section"
                )


NON_LATIN_SCRIPT = re.compile(
    r"[\u0370-\u052f\u0590-\u08ff\u3040-\u30ff\u3400-\u9fff]"
)

EVENT_LABELS = {
    "bombing": "an explosion or bombing-related incident",
    "kinetic_strike": "strike activity",
    "sabotage": "suspected sabotage",
    "electronic_warfare": "electronic-warfare activity",
    "cyber_attack": "a cyber incident",
    "espionage": "espionage-related activity",
    "airspace_incursion": "an airspace incident",
    "exercise": "military exercise activity",
    "civil_unrest": "civil unrest",
    "security_operation": "a security operation",
    "diplomatic": "diplomatic activity",
    "unclassified_reporting": "a security-related development",
}


def _clean_english_text(value: str | None, limit: int = 260) -> str:
    """Return readable English source text, never raw HTML or non-Latin copy."""
    text = html.unescape(re.sub(r"<[^>]+>", " ", value or ""))
    text = re.sub(r"\s+", " ", text).strip()
    if not text or NON_LATIN_SCRIPT.search(text):
        return ""
    if len(text) <= limit:
        return text
    shortened = text[:limit].rsplit(" ", 1)[0].rstrip(" ,;:-")
    return shortened + "…"


def _article_description(article: Article) -> str:
    title = _clean_english_text(article.title, 180)
    category = (article.category or "security reporting").replace("_", " ")
    location = article.country or "the area"
    if not title:
        title = f"{EVENT_LABELS.get(article.category, category)} in {location}"
    summary = _clean_english_text(article.summary, 240)
    detail = f"{title}."
    if summary and summary.lower() not in title.lower() and title.lower() not in summary.lower():
        detail += f" {summary}."
    return detail


def _join_ranked(counter: Counter, limit: int = 3) -> str:
    ranked = counter.most_common(limit)
    if not ranked:
        return "no confirmed geographic concentration"
    return ", ".join(f"{name} ({count})" for name, count in ranked)


def _fallback_window_assessment(articles: list[Article], window: str, days: float) -> tuple[str, str, str]:
    """Create a detailed, source-faithful synopsis without an external model."""
    count = len(articles)
    if not articles:
        return (
            f"No material change. No qualifying significant development was identified in the {window} window. "
            "The absence of a new event in this period does not by itself indicate a change in the underlying security posture.",
            "The available operating picture remains unchanged from the previously established baseline. "
            "There is no new, geographically attributable activity on which to base a revised operational judgement.",
            "No material change. Maintain routine monitoring for a corroborated event, a change in military or security posture, "
            "or a sustained increase in relevant activity.",
        )

    categories = Counter((a.category or "security reporting").replace("_", " ") for a in articles)
    countries = Counter(a.country for a in articles if a.country)
    high_severity = sum(1 for a in articles if (a.severity or 0) >= 4)
    reliable = sum(
        1 for a in articles
        if a.source and a.source.reliability in {"official", "established_media"}
    )
    cutoff = datetime.utcnow() - timedelta(days=days / 2)
    recent_half = sum(1 for a in articles if a.published_at >= cutoff)
    earlier_half = count - recent_half
    if recent_half >= max(earlier_half + 2, int(earlier_half * 1.35)):
        tempo = "higher in the most recent half of the window"
    elif earlier_half >= max(recent_half + 2, int(recent_half * 1.35)):
        tempo = "lower in the most recent half of the window"
    else:
        tempo = "broadly even across the two halves of the window"

    top_categories = _join_ranked(categories)
    top_countries = _join_ranked(countries)
    primary_theme = categories.most_common(1)[0][0]
    strategic = (
        f"The {window} picture contains {count} distinct significant developments, led by {top_categories}. "
        f"{high_severity} developments carry a high or critical severity marker, while {reliable} are supported by official or established-media reporting. "
        f"Activity was {tempo}. The aggregate picture therefore keeps {primary_theme} as the principal reported driver of risk, "
        "but reporting volume alone is insufficient to establish a broader change in intent or strategic trajectory."
    )

    lead_items = " ".join(
        f"Priority {index}: {_article_description(article)}"
        for index, article in enumerate(articles[:3], start=1)
    )
    operational = (
        f"Operationally, activity was concentrated in {top_countries}, with the strongest functional concentration in {top_categories}. "
        f"{lead_items} These developments define the current operating picture; events lacking a confirmed location or stronger corroboration "
        "should not be used to infer activity across the whole AO."
    )

    tactical_items = " ".join(
        f"{index}) {_article_description(article)}"
        for index, article in enumerate(articles[:5], start=1)
    )
    tactical = (
        f"The immediate priorities are: {tactical_items} "
        f"Near-term monitoring should test whether the recent {primary_theme} pattern persists, spreads beyond {top_countries}, "
        "or is followed by official posture changes, additional casualties, infrastructure disruption or retaliatory action. "
        "Single-source claims and untranslated source material have not been used as the basis for a stronger judgement."
    )
    return strategic, operational, tactical


def generate_ao_synopses(db: Session, ao: str) -> list:
    """One LLM call produces all 4 window synopses for a single AO."""
    window_articles = {w: _window_articles(db, ao, days) for w, days in WINDOWS.items()}

    sections = []
    for w in WINDOWS:
        arts = window_articles[w]
        sections.append(
            f"=== Window: last {w} ({len(arts)} qualifying items) ===\n"
            f"{_format_articles(arts)}"
        )

    user_prompt = (
        f"AO: {AO_LABELS.get(ao, ao)}\n\n"
        + "\n\n".join(sections)
        + "\n\nProduce the synopsis now. Remember: respond with ONLY the raw JSON "
          "object, starting with { and ending with }, no markdown, no fences."
    )

    raw = complete(
        SYSTEM_PROMPT,
        user_prompt,
        max_tokens=5000,
        json_schema=SYNOPSIS_SCHEMA,
    )
    logger.debug("Raw synopsis response for %s (first 200 chars): %s", ao, raw[:200])

    parsed = _extract_json(raw)
    if not parsed:
        logger.warning("Could not extract valid JSON from synopsis response for %s", ao)
    _validate_synopsis(
        parsed,
        {window: len(articles) for window, articles in window_articles.items()},
    )

    results = []
    for window in WINDOWS:
        window_data = parsed[window]
        synopsis = Synopsis(
            ao=ao,
            window=window,
            strategic=window_data.get("strategic", ""),
            operational=window_data.get("operational", ""),
            tactical=window_data.get("tactical", ""),
            generated_at=datetime.utcnow(),
            source_article_count=len(window_articles[window]),
        )
        db.add(synopsis)
        results.append(synopsis)

    db.commit()
    for s in results:
        db.refresh(s)
    return results


def generate_fallback_ao_synopses(db: Session, ao: str) -> list:
    """Persist a conservative, data-derived synopsis when the model is unavailable."""
    results = []
    generated_at = datetime.utcnow()
    for window, days in WINDOWS.items():
        articles = _window_articles(db, ao, days)
        count = len(articles)
        strategic, operational, tactical = _fallback_window_assessment(
            articles, window, days
        )
        synopsis = Synopsis(
            ao=ao,
            window=window,
            strategic=strategic,
            operational=operational,
            tactical=tactical,
            generated_at=generated_at,
            source_article_count=count,
        )
        db.add(synopsis)
        results.append(synopsis)
    db.commit()
    for synopsis in results:
        db.refresh(synopsis)
    return results


def generate_all_synopses(db: Session, delay_seconds: float = 5.0):
    """One isolated LLM call per AO, producing all windows for that AO."""
    results = []
    aos = list(AO_LABELS.keys())
    for i, ao in enumerate(aos):
        try:
            results.extend(generate_ao_synopses(db, ao))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Model synopsis failed for %s; using isolated fallback: %s", ao, exc)
            db.rollback()
            results.extend(generate_fallback_ao_synopses(db, ao))
        if i < len(aos) - 1:
            time.sleep(delay_seconds)
    return results
