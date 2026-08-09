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

Write the intelligence, not the collection process. Do not state source counts, \
event counts, severity totals, reliability-tier totals or phrases such as \
"the reporting set contains". Use that metadata internally to calibrate confidence. \
Lead with what changed, what it means for the AO and the likely near-term direction. \
The prose must read as if drafted by an experienced defence analyst, with facts \
and assessment integrated naturally rather than presented as dashboard statistics.

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
    articles = (
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
    selected = _select_relevant_articles(articles, limit=100)
    selected.sort(
        key=lambda article: (
            _ao_relevance_score(article),
            article.source.reliability in {"official", "established_media"} if article.source else False,
            article.severity or 0,
            article.published_at,
        ),
        reverse=True,
    )
    return selected


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

AO_CONTEXT = {
    "AO_HIGH_NORTH": "regional defence posture, border security, critical infrastructure and resilience against grey-zone pressure",
    "AO_EUROPE": "battlefield tempo, long-range strike exchange, force protection and wider eastern European spillover",
    "AO_BALKANS": "political stability, inter-ethnic friction, border security, allied missions and external influence",
    "AO_LEVANT": "cross-border escalation, proxy activity, state security posture and the risk of regional spillover",
}

STRATEGIC_JUDGEMENTS = {
    "bombing": "The security environment remains vulnerable to explosive violence and the possibility of follow-on attacks.",
    "kinetic strike": "The security environment remains dominated by kinetic activity, sustaining pressure on force protection, infrastructure and escalation management.",
    "sabotage": "Hybrid risk remains elevated, particularly around infrastructure and other targets where attribution can be obscured.",
    "electronic warfare": "Grey-zone pressure remains the principal concern, with electronic-warfare activity continuing to challenge navigation and communications resilience.",
    "cyber attack": "Cyber activity remains an important vector for disruption and may support wider hybrid pressure if paired with physical or information operations.",
    "espionage": "Counter-intelligence pressure remains material, with continued implications for sensitive institutions, personnel and allied activity.",
    "airspace incursion": "Air-domain friction remains a source of escalation risk and places continued demands on surveillance and attribution.",
    "exercise": "Military activity is primarily signalling readiness and posture; the key judgement is whether it remains bounded or transitions into a more enduring deployment.",
    "civil unrest": "The immediate security concern is political and public-order instability, particularly if mobilisation broadens or becomes violent.",
    "security operation": "State security activity remains focused on containing localised threats and preventing them from developing into a wider challenge.",
    "diplomatic": "Diplomatic signalling is shaping the regional environment, although political engagement has not yet produced a demonstrable operational change.",
    "security reporting": "The available developments do not yet establish a single dominant trajectory, but they warrant continued monitoring for convergence or escalation.",
}

NEAR_TERM_INDICATORS = {
    "bombing": "additional devices, claims of responsibility, changes in protective posture or retaliatory action",
    "kinetic strike": "follow-on strikes, changes in target selection, force movements, infrastructure disruption or retaliatory action",
    "sabotage": "reconnaissance around infrastructure, repeated access attempts, unexplained outages or coordinated attribution narratives",
    "electronic warfare": "wider navigation or communications disruption, military attribution, geographic spread or protective countermeasures",
    "cyber attack": "repeat intrusions, service disruption, coordinated information activity or evidence of state direction",
    "espionage": "further arrests, diplomatic expulsions, exposed networks or changes in counter-intelligence posture",
    "airspace incursion": "repeat incursions, air-policing changes, formal attribution or more assertive interception",
    "exercise": "extension beyond announced limits, dispersal, live-fire activity or an enduring force presence",
    "civil unrest": "larger mobilisation, geographic spread, violence, emergency measures or security-force reinforcement",
    "security operation": "repeat raids, additional detentions, weapons recoveries or a sustained security presence",
    "diplomatic": "formal agreements, altered defence posture, sanctions, breakdown in talks or coordinated allied statements",
    "security reporting": "corroborated follow-on activity, clearer attribution, geographic spread or a change in official posture",
}

AO_SCOPE = {
    "AO_HIGH_NORTH": {
        "terms": {"arctic", "high north", "finland", "finnish", "norway", "norwegian", "sweden", "swedish", "denmark", "danish", "iceland", "greenland", "svalbard", "baltic", "estonia", "estonian", "latvia", "latvian", "lithuania", "lithuanian", "kaliningrad", "murmansk"},
        "countries": {"Finland", "Norway", "Sweden", "Denmark", "Iceland", "Estonia", "Latvia", "Lithuania", "Baltic Sea", "Greenland"},
    },
    "AO_EUROPE": {
        "terms": {"ukraine", "ukrainian", "russia", "russian", "belarus", "belarusian", "poland", "polish", "moldova", "moldovan", "romania", "romanian", "slovakia", "slovak", "czech", "hungary", "hungarian", "germany", "german", "leipzig", "belgorod", "odesa", "kyiv", "black sea"},
        "countries": {"Ukraine", "Russia", "Belarus", "Poland", "Moldova", "Romania", "Slovakia", "Czechia", "Hungary", "Germany", "Black Sea"},
    },
    "AO_BALKANS": {
        "terms": {"balkan", "albania", "albanian", "bosnia", "bosnian", "bulgaria", "bulgarian", "croatia", "croatian", "greece", "greek", "kosovo", "montenegro", "macedonia", "serbia", "serbian", "slovenia", "slovenian", "belgrade", "sarajevo", "pristina", "republika srpska"},
        "countries": {"Albania", "Bosnia and Herzegovina", "Bulgaria", "Croatia", "Greece", "Kosovo", "Montenegro", "North Macedonia", "Serbia", "Slovenia"},
    },
    "AO_LEVANT": {
        "terms": {"levant", "lebanon", "lebanese", "jordan", "jordanian", "israel", "israeli", "palestinian", "gaza", "west bank", "syria", "syrian", "iran", "iranian", "iraq", "iraqi", "yemen", "yemeni", "houthi", "hezbollah", "hamas", "red sea"},
        "countries": {"Lebanon", "Jordan", "Israel", "Palestine", "Gaza", "West Bank", "Syria", "Iran", "Iraq", "Yemen", "Red Sea"},
    },
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


def _summary_description(article: Article) -> str:
    summary = _clean_english_text(article.summary, 700)
    if summary:
        sentences = re.split(r"(?<=[.!?])\s+", summary)
        selected = []
        for sentence in sentences:
            if not selected and len(sentence.split()) > 55:
                sentence = " ".join(sentence.split()[:55]).rstrip(" ,;:-") + "…"
            if selected and len(" ".join(selected + [sentence]).split()) > 55:
                break
            selected.append(sentence)
            if len(selected) == 2:
                break
        fact = " ".join(selected).strip()
        if fact:
            return fact.rstrip(".") + "."
    return ""


def _article_description(article: Article) -> str:
    title = _clean_english_text(article.title, 180)
    category = (article.category or "security reporting").replace("_", " ")
    location = article.country or "the area"
    if not title:
        title = f"{EVENT_LABELS.get(article.category, category)} was reported in {location}"
    summary = _summary_description(article)
    title_words = set(re.findall(r"[a-z0-9]+", title.lower()))
    summary_words = set(re.findall(r"[a-z0-9]+", summary.lower())) if summary else set()
    overlap = len(title_words & summary_words) / max(1, len(title_words))
    if summary and overlap < 0.72:
        return f"{title.rstrip('.')}. {summary}"
    if summary:
        return f"{title}."
    return f"{title}."


def _reported_sentence(article: Article) -> str:
    reliability = article.source.reliability if article.source else "unverified"
    detail = _article_description(article).rstrip(".")
    if reliability == "unverified":
        return f"Details remain unconfirmed, but {detail}."
    if reliability == "regional_specialist":
        return f"Available information indicates that {detail}."
    return detail + "."


def _select_relevant_articles(articles: list[Article], limit: int = 100) -> list[Article]:
    """Remove obvious classification noise while retaining thin but relevant reporting."""
    selected = []
    seen = set()
    operational_terms = {
        "security force", "police", "military", "intelligence", "border guard",
        "raid", "detain", "arrested", "weapons", "operation", "checkpoint",
        "interdiction", "counter-terror", "counterterror", "patrol",
    }
    security_terms = operational_terms | {
        "strike", "drone", "missile", "sabotage", "cyber", "jamming",
        "spoofing", "explosion", "unrest", "protest", "exercise", "nato",
        "defence", "defense", "infrastructure", "airspace", "naval",
    }
    for article in articles:
        title_text = _clean_english_text(article.title, 300).lower()
        text = " ".join(filter(None, [article.title, article.summary])).lower()
        if any(marker in title_text for marker in ("mshale", "years ago today", "anniversary")):
            continue
        ao = getattr(article, "ao", "")
        scope = AO_SCOPE.get(ao)
        if scope:
            title_in_scope = any(term in title_text for term in scope["terms"])
            country_in_scope = getattr(article, "country", None) in scope["countries"]
            text_in_scope = any(term in text for term in scope["terms"])
            title_points_elsewhere = any(
                term in title_text
                for other_ao, other_scope in AO_SCOPE.items()
                if other_ao != ao
                for term in other_scope["terms"]
            )
            if title_points_elsewhere and not title_in_scope:
                continue
            if title_points_elsewhere and title_in_scope:
                target_positions = [title_text.find(term) for term in scope["terms"] if term in title_text]
                other_positions = [
                    title_text.find(term)
                    for other_ao, other_scope in AO_SCOPE.items()
                    if other_ao != ao
                    for term in other_scope["terms"]
                    if term in title_text
                ]
                if (
                    other_positions
                    and target_positions
                    and min(other_positions) < min(target_positions)
                    and min(target_positions) > len(title_text) * 0.5
                ):
                    continue
            if not title_in_scope and not country_in_scope and not text_in_scope:
                continue
        if article.category == "security_operation" and not any(term in title_text for term in operational_terms):
            continue
        if article.category in {None, "unclassified_reporting"} and not any(term in title_text for term in security_terms):
            continue
        fingerprint = re.sub(r"[^a-z0-9]+", " ", (article.title or "").lower()).strip()[:100]
        if fingerprint and fingerprint in seen:
            continue
        if fingerprint:
            seen.add(fingerprint)
        selected.append(article)
        if len(selected) >= limit:
            break
    return selected


def _ao_relevance_score(article: Article) -> int:
    """Prefer developments whose headline, rather than metadata alone, is AO-specific."""
    scope = AO_SCOPE.get(getattr(article, "ao", ""))
    if not scope:
        return 1
    title = _clean_english_text(article.title, 300).lower()
    if any(term in title for term in scope["terms"]):
        return 3
    if getattr(article, "country", None) in scope["countries"]:
        return 2
    return 1


def _human_list(values: list[str]) -> str:
    values = [value for value in values if value]
    if not values:
        return "the AO"
    if len(values) == 1:
        return values[0]
    if len(values) == 2:
        return f"{values[0]} and {values[1]}"
    return f"{', '.join(values[:-1])}, and {values[-1]}"


def _fallback_window_assessment(articles: list[Article], window: str, days: float) -> tuple[str, str, str]:
    """Create defence-analyst prose without exposing collection mechanics."""
    count = len(articles)
    if not articles:
        return (
            f"No material change was identified during the {window} period. The established regional security posture remains in place, "
            "and the absence of a new significant development does not by itself indicate a reduction in the underlying threat.",
            "The operating picture remains consistent with the previously established baseline. No new development warrants a change to the current operational judgement or readiness posture.",
            "No material change. Maintain routine awareness for a change in military posture, a corroborated security incident, "
            "or renewed pressure against critical infrastructure and border systems.",
        )

    categories = Counter((a.category or "security reporting").replace("_", " ") for a in articles)
    countries = [name for name, _ in Counter(a.country for a in articles if a.country).most_common(3)]
    cutoff = datetime.utcnow() - timedelta(days=days / 2)
    recent_half = sum(1 for a in articles if a.published_at >= cutoff)
    earlier_half = count - recent_half
    if recent_half >= max(earlier_half + 2, int(earlier_half * 1.35)):
        tempo = "higher in the most recent half of the window"
    elif earlier_half >= max(recent_half + 2, int(recent_half * 1.35)):
        tempo = "lower in the most recent half of the window"
    else:
        tempo = "broadly even across the two halves of the window"

    primary_theme = categories.most_common(1)[0][0]
    secondary_theme = categories.most_common(2)[1][0] if len(categories) > 1 else None
    strategic_judgement = STRATEGIC_JUDGEMENTS.get(
        primary_theme, STRATEGIC_JUDGEMENTS["security reporting"]
    )
    context = AO_CONTEXT.get(
        getattr(articles[0], "ao", ""),
        "regional security posture and escalation risk",
    )
    lead_development = _reported_sentence(articles[0])
    strategic = (
        f"{strategic_judgement} The principal implications concern {context}. "
        f"{lead_development} "
        + (
            f"Taken together, the interaction between {primary_theme} and {secondary_theme} activity warrants close attention, "
            if secondary_theme else f"The persistence of {primary_theme} activity warrants close attention, "
        )
        + "although the available developments do not yet demonstrate a fundamental shift in strategic intent."
    )

    geography = _human_list(countries)
    operational_facts = " ".join(_reported_sentence(article) for article in articles[:4])
    operational = (
        f"Operational activity is centred on {geography}. {operational_facts} "
        f"The pattern was {tempo}, keeping the immediate focus on {primary_theme} activity and its potential to affect adjacent security tasks. "
        "The available evidence supports a localised assessment; it does not yet justify treating the activity as uniform across the entire AO."
    )

    indicators = NEAR_TERM_INDICATORS.get(primary_theme, NEAR_TERM_INDICATORS["security reporting"])
    tactical = (
        f"Tactically, the immediate concern is whether the latest developments remain contained or begin to affect wider force-protection and resilience tasks. "
        f"The current disposition favours continuity: authorities and operators are likely to manage the immediate effects within existing arrangements unless follow-on activity exposes a broader vulnerability. "
        f"The key question is whether the activity remains isolated or develops into a sustained {primary_theme} pattern. "
        f"Indicators of material change would include {indicators}. Until those indicators emerge, the most defensible judgement is continued localised friction rather than AO-wide escalation."
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
