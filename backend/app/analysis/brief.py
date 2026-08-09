import logging
import re
import time
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.config import settings
from app.models import Article, Brief, Synopsis
from app.analysis.llm_client import complete
from app.analysis.trends import category_trend_summary

logger = logging.getLogger("sentinel.analysis.brief")

AO_CONFIG = {
    "AO_HIGH_NORTH": {
        "title": "AO HIGH NORTH DAILY ANALYST BRIEF",
        "area": "High North / Finland / Baltic states",
        "focus": "hybrid and grey-zone activity, regional defence posture, border security, critical infrastructure and military activity affecting the High North, Finland and the Baltic states",
    },
    "AO_EUROPE": {
        "title": "AO UKRAINE & EASTERN EUROPE DAILY ANALYST BRIEF",
        "area": "Ukraine / eastern and central Europe",
        "focus": "the war in Ukraine, military and security developments across eastern and central Europe, and direct regional spillover affecting this area",
    },
    "AO_BALKANS": {
        "title": "AO BALKANS DAILY ANALYST BRIEF",
        "area": "The Balkans",
        "focus": "military posture, political-security instability, inter-ethnic tension, border security, organised security threats, NATO and EU missions, and malign influence affecting the Balkans",
    },
    "AO_LEVANT": {
        "title": "AO LEVANT DAILY ANALYST BRIEF",
        "area": "Broader Middle East — Lebanon / Jordan focus",
        "focus": "state, proxy and cross-border activity affecting Lebanon, Jordan and the surrounding operational environment",
    },
}

SYSTEM_PROMPT = """You are a senior military intelligence analyst producing a daily \
area brief for a fusion cell, drafted entirely from open-source reporting (OSINT). \
Audience: watch officers and analysts who need a fast, decision-useful read at shift \
handover. Use formal military-intelligence prose and standard hedging language for \
confidence. Never invent facts, units, casualty numbers or attributions not present \
in the supplied reporting. This is a civilian analytical product built from public \
sources; never claim access to classified or sensitive collection.

LANGUAGE RULE: Write the entire product in clear British English. Translate and \
paraphrase any non-English source reporting into English. Never reproduce Cyrillic, \
Arabic, Hebrew, Greek or other non-Latin source text in headings, bullets or prose.

ABSOLUTE SCOPE RULE: You are writing about ONE Area of Operation only. Use only the \
reporting supplied in this prompt. Do not mention, compare with, infer from, or add \
events from any other Area of Operation. If reporting is thin, state the collection \
gap instead of broadening the geographic scope.

Weight claims using the supplied reliability tiers (official, established_media, \
regional_specialist, unverified). Duplicate reporting has already been collapsed. \
Use the 14-day trend summary to identify supported patterns without overstating \
small samples. Distinguish reported facts from your assessment.

Follow the exact markdown structure supplied by the user prompt. Keep the executive \
summary to 3-5 sentences and the full product to 500-750 words. Paraphrase source \
material; never quote it verbatim. Prioritise what changed, why it matters, likely \
near-term implications, warning indicators and explicit collection gaps."""


FACT_CHECK_SYSTEM_PROMPT = """You are reviewing a single-AO OSINT analyst brief. \
Compare the draft only with the source reporting supplied. Flag: (1) unsupported \
claims, figures, names or attribution; (2) confidence stronger than the source tiers \
justify; and (3) any event or geographic claim outside the named AO. Output a short \
bulleted list of concerns. If none exist, output exactly: \
"No discrepancies identified against the provided source set." Do not rewrite the brief."""

REVISION_SYSTEM_PROMPT = """You are the senior editor of a single-AO OSINT analyst \
brief. Revise the supplied draft to resolve every fact-check concern. Preserve the \
required markdown structure and AO boundary. Remove or soften unsupported claims; do \
not replace them with new claims. Use only the authorised source reporting. Return \
only the complete revised brief, in English, with no preamble or editorial commentary. \
Translate or paraphrase all non-English material; do not reproduce non-Latin text."""

REQUIRED_SECTIONS = (
    "## 1. EXECUTIVE SUMMARY",
    "## 2. SITUATION OVERVIEW",
    "## 3. KEY DEVELOPMENTS",
    "## 4. ASSESSMENT",
    "## 5. OUTLOOK & INDICATORS",
    "## 6. COLLECTION GAPS & CONFIDENCE",
)

NON_LATIN_SCRIPT = re.compile(
    r"[\u0370-\u052f\u0590-\u08ff\u3040-\u30ff\u3400-\u9fff]"
)

EVENT_LABELS = {
    "bombing": "Bombing",
    "kinetic_strike": "Kinetic strike",
    "sabotage": "Suspected sabotage",
    "electronic_warfare": "Electronic-warfare activity",
    "cyber_attack": "Cyber attack",
    "espionage": "Espionage-related activity",
    "airspace_incursion": "Airspace incursion",
    "exercise": "Military exercise",
    "civil_unrest": "Civil unrest",
    "security_operation": "Security operation",
    "diplomatic": "Diplomatic activity",
    "unclassified_reporting": "Security-related reporting",
}


def _recent_articles(db: Session, ao: str, hours: int = 48, limit: int = 100):
    since = datetime.utcnow() - timedelta(hours=hours)
    return (
        db.query(Article)
        .filter(
            Article.ao == ao,
            Article.published_at >= since,
            Article.is_cluster_primary == True,  # noqa: E712
        )
        .order_by(Article.severity.desc(), Article.published_at.desc())
        .limit(limit)
        .all()
    )


def _format_articles(articles) -> str:
    lines = []
    for article in articles:
        reliability = article.source.reliability if article.source else "unverified"
        lines.append(
            f"- [{article.published_at.isoformat()}Z] ({article.category}, "
            f"sev {article.severity}, sigact={article.is_sigact}, "
            f"reliability={reliability}) {article.title} — "
            f"{(article.summary or '')[:280]}"
        )
    return "\n".join(lines) if lines else "(no reporting in this window)"


def _brief_structure(ao: str, period_start: datetime, period_end: datetime) -> str:
    config = AO_CONFIG[ao]
    return f"""Write ONLY the {config['title']}.
Area: {config['area']}
Analytical focus: {config['focus']}

Use this exact markdown structure:

# {config['title']}
**Classification:** UNCLASSIFIED // OPEN SOURCE ONLY
**Period covered:** {period_start.strftime('%Y-%m-%d %H:%MZ')} to {period_end.strftime('%Y-%m-%d %H:%MZ')}

## 1. EXECUTIVE SUMMARY
<bottom line up front for this AO only>

## 2. SITUATION OVERVIEW
<current operating picture and material change during the reporting period>

## 3. KEY DEVELOPMENTS
- <prioritised developments, with confidence calibrated to source reliability>

## 4. ASSESSMENT
<what the reporting means; clearly distinguish assessment from reported fact>

## 5. OUTLOOK & INDICATORS
- **Short term (0-72h):**
- **Medium term (1-4 weeks):**
- **Long term (1-6 months):**
- **Indicators to watch:**

## 6. COLLECTION GAPS & CONFIDENCE
<specific gaps, source limitations and overall confidence for this AO only>"""


def _validate_brief(content: str, ao: str) -> None:
    """Do not publish truncated, malformed or cross-AO model output."""
    if not isinstance(content, str) or len(content.split()) < 350:
        raise ValueError(f"{ao} brief was truncated or too short")
    missing = [section for section in REQUIRED_SECTIONS if section not in content]
    if missing:
        raise ValueError(f"{ao} brief is missing required sections: {', '.join(missing)}")
    if NON_LATIN_SCRIPT.search(content):
        raise ValueError(f"{ao} brief contains untranslated non-English script")
    current_label = AO_CONFIG[ao]["title"].removesuffix(" DAILY ANALYST BRIEF")
    for other_ao, other_config in AO_CONFIG.items():
        if other_ao == ao:
            continue
        other_label = other_config["title"].removesuffix(" DAILY ANALYST BRIEF")
        if other_label in content.upper():
            raise ValueError(
                f"{current_label} brief crossed the AO boundary by mentioning {other_label}"
            )


def _english_development_title(article: Article) -> str:
    """Use an English title or a factual English descriptor for foreign text."""
    title = (article.title or "").strip()
    if title and not NON_LATIN_SCRIPT.search(title):
        return title
    event = EVENT_LABELS.get(article.category, "Security-related event")
    location = article.country or AO_CONFIG.get(article.ao, {}).get("area") or "the area"
    return f"{event} reported in {location} (severity {article.severity})"


def _build_fallback_content(
    db: Session,
    ao: str,
    articles: list,
    trend: str,
    period_start: datetime,
    period_end: datetime,
) -> str:
    """Build a source-faithful brief when the analysis provider is unavailable."""
    config = AO_CONFIG[ao]
    synopsis = (
        db.query(Synopsis)
        .filter(Synopsis.ao == ao, Synopsis.window == "24h")
        .order_by(Synopsis.generated_at.desc())
        .first()
    )
    strategic = synopsis.strategic if synopsis else "No generated synopsis is available for this reporting period."
    operational = synopsis.operational if synopsis else "The current event list is the available operating picture."
    tactical = synopsis.tactical if synopsis else "No additional tactical assessment is available."
    developments = []
    for article in articles[:10]:
        source_name = article.source.name if article.source else "Unknown source"
        reliability = article.source.reliability if article.source else "unverified"
        developments.append(
            f"- **{_english_development_title(article)}** — "
            f"{source_name}; reliability: {reliability}."
        )
    if not developments:
        developments.append("- No qualifying reporting was collected in this period.")

    return f"""# {config['title']}
**Classification:** UNCLASSIFIED // OPEN SOURCE ONLY
**Period covered:** {period_start.strftime('%Y-%m-%d %H:%MZ')} to {period_end.strftime('%Y-%m-%d %H:%MZ')}

## 1. EXECUTIVE SUMMARY
{strategic}

## 2. SITUATION OVERVIEW
{operational}

## 3. KEY DEVELOPMENTS
{chr(10).join(developments)}

## 4. ASSESSMENT
{tactical}

The trailing 14-day event pattern is:
{trend}

## 5. OUTLOOK & INDICATORS
- **Short term (0-72h):** Continue monitoring the reported event set for corroboration, escalation or material change.
- **Medium term (1-4 weeks):** Current open reporting does not support a higher-confidence forecast beyond the assessment above.
- **Long term (1-6 months):** Insufficient evidence is available in this collection window for a defensible long-range judgment.
- **Indicators to watch:** Corroboration from official or established sources; changes in event frequency, severity or geographic concentration.

## 6. COLLECTION GAPS & CONFIDENCE
This provider-independent brief is assembled only from the latest validated {ao} synopsis and the current isolated source set. Reporting gaps, unverified single-source claims and events without confirmed locations require analyst review. No reporting from another AO has been used."""


def generate_fallback_ao_brief(db: Session, ao: str) -> Brief:
    """Persist a deterministic AO brief without making an external model call."""
    if ao not in AO_CONFIG:
        raise ValueError(f"Unsupported AO: {ao}")
    articles = _recent_articles(db, ao)
    period_end = datetime.utcnow()
    period_start = period_end - timedelta(hours=48)
    content = _build_fallback_content(
        db,
        ao,
        articles,
        category_trend_summary(db, ao),
        period_start,
        period_end,
    )
    brief = Brief(
        ao=ao,
        generated_at=datetime.utcnow(),
        content=content,
        fact_check_notes=(
            "Provider-independent brief assembled from the validated AO synopsis "
            "and isolated source records; analyst review required."
        ),
        source_article_count=len(articles),
    )
    db.add(brief)
    db.commit()
    db.refresh(brief)
    return brief


def generate_ao_brief(db: Session, ao: str, run_fact_check: bool = None) -> Brief:
    """Generate and store one geographically isolated AO brief."""
    if ao not in AO_CONFIG:
        raise ValueError(f"Unsupported AO: {ao}")
    if run_fact_check is None:
        run_fact_check = settings.ENABLE_FACT_CHECK

    articles = _recent_articles(db, ao)
    period_end = datetime.utcnow()
    period_start = period_end - timedelta(hours=48)
    trend = category_trend_summary(db, ao)
    config = AO_CONFIG[ao]

    source_block = (
        f"AO BOUNDARY: {ao} — {config['area']}\n"
        f"Only the material below is authorised for this brief.\n\n"
        f"=== {ao} source reporting ({len(articles)} distinct events) ===\n"
        f"{_format_articles(articles)}\n\n"
        f"=== {ao} 14-day trend summary ===\n{trend}\n"
    )
    user_prompt = (
        _brief_structure(ao, period_start, period_end)
        + "\n\n=== AUTHORISED SOURCE MATERIAL ===\n"
        + source_block
        + f"\nProduce the {ao} brief now. Do not mention any other AO."
    )
    content = complete(
        SYSTEM_PROMPT,
        user_prompt,
        max_tokens=6000,
        thinking_level="low",
    )
    _validate_brief(content, ao)

    fact_check_notes = None
    if run_fact_check:
        time.sleep(4.0)
        try:
            fc_prompt = (
                f"AO UNDER REVIEW: {ao}\n\n=== DRAFT BRIEF ===\n{content}\n\n"
                f"=== AUTHORISED SOURCE REPORTING ===\n{source_block}"
            )
            fact_check_notes = complete(
                FACT_CHECK_SYSTEM_PROMPT,
                fc_prompt,
                max_tokens=1000,
                thinking_level="low",
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Fact-check pass failed for %s: %s", ao, exc)
            fact_check_notes = "Fact-check pass could not be completed this cycle."
        else:
            if not fact_check_notes.strip().startswith("No discrepancies identified"):
                time.sleep(4.0)
                revision_prompt = (
                    f"AO: {ao}\n\n=== DRAFT BRIEF ===\n{content}\n\n"
                    f"=== FACT-CHECK CONCERNS ===\n{fact_check_notes}\n\n"
                    f"=== AUTHORISED SOURCE REPORTING ===\n{source_block}"
                )
                revised_content = complete(
                    REVISION_SYSTEM_PROMPT,
                    revision_prompt,
                    max_tokens=6000,
                    thinking_level="low",
                )
                _validate_brief(revised_content, ao)
                content = revised_content
                fact_check_notes = (
                    "Draft revised to address the automated fact-check findings:\n\n"
                    + fact_check_notes
                )

    brief = Brief(
        ao=ao,
        generated_at=datetime.utcnow(),
        content=content,
        fact_check_notes=fact_check_notes,
        source_article_count=len(articles),
    )
    db.add(brief)
    db.commit()
    db.refresh(brief)
    return brief


def generate_all_briefs(db: Session, delay_seconds: float = 5.0) -> list[Brief]:
    """Generate all four AO products independently, with isolated fallbacks."""
    results = []
    for index, ao in enumerate(AO_CONFIG):
        try:
            results.append(generate_ao_brief(db, ao))
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Model-generated brief failed for %s; using isolated fallback: %s",
                ao,
                exc,
            )
            results.append(generate_fallback_ao_brief(db, ao))
        if index < len(AO_CONFIG) - 1:
            time.sleep(delay_seconds)
    return results


# Backwards-compatible entry point used by the scheduler.
def generate_brief(db: Session, run_fact_check: bool = None) -> list[Brief]:
    if run_fact_check is None:
        return generate_all_briefs(db)
    return [
        generate_ao_brief(db, ao, run_fact_check=run_fact_check)
        for ao in AO_CONFIG
    ]
