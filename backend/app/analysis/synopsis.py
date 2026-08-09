import json
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
"tactical" — each a plain string of 2-5 sentences."""

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
        .order_by(Article.published_at.desc())
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


def _validate_synopsis(parsed: dict) -> None:
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
    _validate_synopsis(parsed)

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
        if not articles:
            strategic = "No material change was identified in qualifying reporting for this period."
            operational = "No distinct significant events were collected for the current window."
            tactical = "Continue routine monitoring for corroborated indicators or a change in reporting volume."
        else:
            categories = Counter((article.category or "security reporting").replace("_", " ") for article in articles)
            countries = Counter(article.country for article in articles if article.country)
            top_category = categories.most_common(1)[0][0]
            top_country = countries.most_common(1)[0][0] if countries else "the AO"
            high_severity = sum(1 for article in articles if (article.severity or 0) >= 4)
            strategic = (
                f"{count} distinct significant events were collected in the {window} window; "
                f"{high_severity} were assessed at high or critical severity."
            )
            operational = (
                f"Reporting was most concentrated on {top_category} activity, with the largest "
                f"geographic concentration in {top_country}."
            )
            tactical = (
                "This automated fallback identifies reporting concentration only. Continue monitoring "
                "for corroboration, escalation and geographic spread before drawing a higher-confidence assessment."
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
