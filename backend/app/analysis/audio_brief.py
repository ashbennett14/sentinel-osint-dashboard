"""Build and persist the daily, chaptered SENTINEL audio briefing."""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import sys
import tempfile
import unicodedata
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.analysis.brief import AO_CONFIG, EVENT_LABELS, NON_LATIN_SCRIPT
from app.analysis.llm_client import complete
from app.analysis.synopsis import _extract_json
from app.config import settings
from app.models import Article, AudioBrief, Brief, Source, Synopsis
from app.storage import cloud_storage_enabled, delete_audio, upload_audio

logger = logging.getLogger("sentinel.analysis.audio")


AO_ORDER = ("AO_HIGH_NORTH", "AO_EUROPE", "AO_BALKANS", "AO_LEVANT")
AO_AUDIO = {
    "AO_HIGH_NORTH": ("high-north", "High North, Finland and the Baltic states"),
    "AO_EUROPE": ("eastern-europe", "Ukraine and Eastern Europe"),
    "AO_BALKANS": ("balkans", "The Balkans"),
    "AO_LEVANT": ("levant", "The Levant"),
}
RELIABILITY_ORDER = {
    "official": 4,
    "established_media": 3,
    "regional_specialist": 2,
    "unverified": 1,
}

PODCAST_KEYS = ("opening", "high-north", "eastern-europe", "balkans", "levant", "closing")
PROHIBITED_SPOKEN_LANGUAGE = re.compile(
    r"(?i)\b(?:sources?|collection|corroborat\w*|confidence|severity|sigacts?|"
    r"open[- ]source|distinct events?|dataset)\b"
)
PODCAST_SCHEMA = {
    "type": "object",
    "properties": {key: {"type": "string"} for key in PODCAST_KEYS},
    "required": list(PODCAST_KEYS),
}
PODCAST_SYSTEM_PROMPT = """Write a short British current-affairs briefing for the ear, not a written assessment.
Lead with what happened: one or two concrete headlines in the opening, then in each regional chapter say what changed, why it matters and what to watch next, only where supported. Begin each regional chapter with a natural mention of the region. Use short, plain spoken sentences. Avoid jargon, generic scene-setting and repeated transitions. Do not read headings, counts, metadata or methodology aloud.
Give consequential stories more time, usually up to 130 words per region. A quieter chapter can be a single sentence. There is no minimum length. Never pad the copy or lift sentences from written assessments. For an empty region use only its name followed by 'No material change.'
Use only supplied facts. Separate confirmed developments, allegations and analysis; retain attribution to relevant officials or institutions when it matters to the claim. Do not name media publishers or discuss sourcing. Do not say the programme name or add a greeting: the producer adds the ident once. End with a brief sign-off. Return only JSON matching the supplied schema."""

BACKEND_DIR = Path(__file__).resolve().parents[2]
PROJECT_DIR = BACKEND_DIR.parent
AUDIO_DIR = BACKEND_DIR / "generated" / "audio"
TTS_PYTHON = BACKEND_DIR / "tts-venv" / "bin" / "python"
TTS_WORKER = PROJECT_DIR / "scripts" / "generate_audio.py"


def _clean_spoken_text(value: str) -> str:
    value = value or ""
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"\[([^]]+)]\([^)]+\)", r"\1", value)
    value = re.sub(r"https?://\S+", " ", value)
    value = re.sub(r"^#{1,6}\s*", "", value, flags=re.MULTILINE)
    value = re.sub(r"^\s*[-*]\s+", "", value, flags=re.MULTILINE)
    value = value.replace("**", "").replace("__", "").replace("`", "")
    for american, british in {
        "defense": "defence",
        "localized": "localised",
        "unauthorized": "unauthorised",
        "neighboring": "neighbouring",
        "prioritize": "prioritise",
    }.items():
        value = re.sub(rf"(?i)\b{american}\b", british, value)
    value = NON_LATIN_SCRIPT.sub("", value)
    value = "".join(character for character in value if unicodedata.category(character) not in ("So", "Cs"))
    value = re.sub(r"\s+", " ", value)
    return value.strip(" -\n")


def _clip_words(value: str, limit: int) -> str:
    words = _clean_spoken_text(value).split()
    if len(words) <= limit:
        return " ".join(words)
    clipped = " ".join(words[:limit])
    sentence_end = max(clipped.rfind("."), clipped.rfind("?"), clipped.rfind("!"))
    if sentence_end >= max(40, len(clipped) // 2):
        return clipped[: sentence_end + 1]
    return clipped.rstrip(",;:-") + "."


def _brief_section(content: str, number: int) -> str:
    match = re.search(
        rf"(?ims)^##\s+{number}\.[^\n]*\n(.*?)(?=^##\s+\d+\.|\Z)",
        content or "",
    )
    return _clean_spoken_text(match.group(1)) if match else ""


def _english_title(article: Article) -> str:
    original = article.title or ""
    title = "" if NON_LATIN_SCRIPT.search(original) else _clean_spoken_text(original)
    if title:
        title = re.sub(r"\s*[,;]?\s+[—-]\s*[\"“].*$", "", title).strip()
        title = re.sub(r"\s+-\s+[^-]{2,80}$", "", title).strip()
        title = re.sub(r"(?i),?\s+[A-Z][A-Za-z .'-]{2,40}\s+says\.?$", ".", title).strip()
        return title
    event = EVENT_LABELS.get(article.category, "Security-related event")
    location = (article.country or AO_CONFIG[article.ao]["area"]).replace(" / ", " and ")
    return f"{event} in {location}"


def _articles_for_period(db: Session, ao: str, start: datetime, end: datetime) -> list[Article]:
    articles = (
        db.query(Article)
        .filter(
            Article.ao == ao,
            Article.published_at >= start,
            Article.published_at <= end,
            Article.is_sigact == True,  # noqa: E712
            Article.is_cluster_primary == True,  # noqa: E712
        )
        .order_by(Article.published_at.desc())
        .limit(100)
        .all()
    )
    return sorted(
        articles,
        key=lambda item: (
            item.severity or 0,
            RELIABILITY_ORDER.get(item.source.reliability if item.source else "unverified", 0),
            item.published_at,
        ),
        reverse=True,
    )


def _latest_synopsis(db: Session, ao: str) -> Synopsis | None:
    return (
        db.query(Synopsis)
        .filter(Synopsis.ao == ao, Synopsis.window == "24h")
        .order_by(Synopsis.generated_at.desc())
        .first()
    )


def _latest_brief(db: Session, ao: str) -> Brief | None:
    return (
        db.query(Brief)
        .filter(Brief.ao == ao)
        .order_by(Brief.generated_at.desc())
        .first()
    )


def _development_text(articles: list[Article]) -> str:
    if not articles:
        return "No qualifying significant events were collected in this area during the reporting period."
    developments = []
    for article in articles[:4]:
        developments.append(f"{_english_title(article).rstrip('.')}.")
    return " ".join(developments)


def _known_source_names(db: Session) -> list[str]:
    aliases = set()
    for (name,) in db.query(Source.name).all():
        if not name:
            continue
        cleaned = name.strip()
        candidates = {
            cleaned,
            re.split(r"(?i)\s+via\s+|\s*\(|\s+[—-]\s+", cleaned, maxsplit=1)[0].strip(),
        }
        aliases.update(candidate for candidate in candidates if len(candidate) >= 4)
    return sorted(aliases, key=len, reverse=True)


def _contains_source_name(value: str, source_names: list[str]) -> bool:
    lowered = (value or "").lower()
    return any(name.lower() in lowered for name in source_names)


def _safe_spoken_sentences(value: str, source_names: list[str], limit: int) -> str:
    """Keep only clean, self-contained sentences for the deterministic fallback."""
    sentences = re.split(r"(?<=[.!?])\s+", _clean_spoken_text(value))
    clean = []
    for sentence in sentences:
        sentence = sentence.strip()
        letters = sum(character.isalpha() and character.isascii() for character in sentence)
        visible = sum(not character.isspace() for character in sentence)
        if (
            sentence
            and letters >= 12
            and letters / max(visible, 1) >= 0.55
            and not PROHIBITED_SPOKEN_LANGUAGE.search(sentence)
            and not _contains_source_name(sentence, source_names)
        ):
            clean.append(sentence)
    return _clip_words(" ".join(clean), limit)


def _chapter_material(db: Session, ao: str, start: datetime, end: datetime) -> tuple[dict, int]:
    _, title = AO_AUDIO[ao]
    articles = _articles_for_period(db, ao, start, end)
    if not articles:
        return {
            "ao": ao,
            "title": title,
            "no_material_change": True,
            "developments": [],
            "situation": "",
            "assessment": "",
            "outlook": "",
        }, 0
    synopsis = _latest_synopsis(db, ao)
    brief = _latest_brief(db, ao)
    material = {
        "ao": ao,
        "title": title,
        "no_material_change": not articles,
        "developments": [
            {
                "title": _english_title(article),
                "summary": _clip_words(_clean_spoken_text(article.summary or ""), 70),
                "location": article.country or "",
            }
            for article in articles[:6]
        ],
        "situation": (
            f"{synopsis.strategic or ''} {synopsis.operational or ''}" if synopsis else ""
        ),
        "assessment": _brief_section(brief.content, 4) if brief else (synopsis.tactical if synopsis else ""),
        "outlook": _brief_section(brief.content, 5) if brief else "",
    }
    return material, len(articles)


def _fallback_developments(material: dict, source_names: list[str]) -> list[str]:
    developments = []
    for item in material["developments"]:
        text = _safe_spoken_sentences(item.get("title", ""), source_names, 28)
        if material["ao"] == "AO_BALKANS" and re.search(r"(?i)\bUkraine\b", text):
            summary = _safe_spoken_sentences(item.get("summary", ""), source_names, 34)
            text = summary if re.search(
                r"(?i)\b(?:Albania|Bosnia|Bulgaria|Croatia|Greece|Kosovo|Montenegro|"
                r"North Macedonia|Serbia|Slovenia|Balkan|Adriatic)\b", summary
            ) else ""
        elif not text:
            text = _safe_spoken_sentences(item.get("summary", ""), source_names, 34)
        if text:
            developments.append(text.rstrip(".!?") + ".")
        if len(developments) >= 2:
            break
    return developments


def _fallback_chapter(material: dict, source_names: list[str]) -> str:
    title = material["title"]
    if material["no_material_change"]:
        return f"{title}. No material change."
    developments = _fallback_developments(material, source_names)
    return f"{title}. " + (" ".join(developments) or "No further detail for now.")


def _fallback_script(materials: dict, source_names: list[str]) -> dict:
    leads = [_fallback_developments(materials[ao], source_names) for ao in AO_ORDER]
    headlines = [regional[0] for regional in leads if regional][:2]
    script = {
        "opening": " ".join(headlines) or "It has been a quiet day across the four regions.",
        "closing": "That's the morning briefing. Thanks for listening.",
    }
    for ao in AO_ORDER:
        key, _ = AO_AUDIO[ao]
        script[key] = _fallback_chapter(materials[ao], source_names)
    return script


def _validate_podcast_copy(script: dict, materials: dict, source_names: list[str]) -> None:
    if not isinstance(script, dict) or any(not isinstance(script.get(key), str) for key in PODCAST_KEYS):
        raise ValueError("Podcast rewrite was incomplete")
    for ao in AO_ORDER:
        key, title = AO_AUDIO[ao]
        if materials[ao]["no_material_change"]:
            script[key] = f"{title}. No material change."
    for key in PODCAST_KEYS:
        value = _clean_spoken_text(script[key])
        if not value:
            raise ValueError(f"Podcast rewrite left {key} empty")
        if PROHIBITED_SPOKEN_LANGUAGE.search(value):
            raise ValueError(f"Podcast rewrite used behind-the-scenes language in {key}")
        if _contains_source_name(value, source_names):
            raise ValueError(f"Podcast rewrite named a publisher in {key}")
        if re.search(r"(?i)(?:^|[.!?]\s+)(?:this is )?Sentinel[.!,:]", value):
            raise ValueError(f"Podcast rewrite repeated the ident in {key}")
        script[key] = value


def _podcast_rewrite(materials: dict, source_names: list[str], local_day: str) -> dict:
    clean_materials = {}
    for ao, material in materials.items():
        clean = dict(material)
        clean["situation"] = _safe_spoken_sentences(material.get("situation", ""), source_names, 180)
        clean["assessment"] = _safe_spoken_sentences(material.get("assessment", ""), source_names, 180)
        clean["outlook"] = _safe_spoken_sentences(material.get("outlook", ""), source_names, 180)
        clean["developments"] = [
            {
                "title": _safe_spoken_sentences(item.get("title", ""), source_names, 45),
                "summary": _safe_spoken_sentences(item.get("summary", ""), source_names, 80),
                "location": item.get("location", ""),
            }
            for item in material["developments"]
        ]
        clean_materials[ao] = clean
    payload = {
        "date": local_day,
        "instructions": {
            "opening": "One or two concrete headlines, up to 45 words. No greeting, date or programme name.",
            "active_chapter": "Name the region, lead with one or two developments, explain why they matter, and offer a specific thing to watch if supported. Usually no more than 130 words. Never pad.",
            "quiet_chapter": "Use only the AO name followed by: No material change.",
            "closing": "One brief natural sign-off.",
        },
        "areas": {AO_AUDIO[ao][0]: clean_materials[ao] for ao in AO_ORDER},
    }
    raw = complete(
        PODCAST_SYSTEM_PROMPT,
        json.dumps(payload, ensure_ascii=False),
        max_tokens=3000,
        json_schema=PODCAST_SCHEMA,
        thinking_level="low",
    )
    script = _extract_json(raw)
    if isinstance(script, dict):
        for key in PODCAST_KEYS:
            if isinstance(script.get(key), str):
                limit = 45 if key == "opening" else 20 if key == "closing" else 145
                script[key] = _safe_spoken_sentences(script[key], source_names, limit)
    _validate_podcast_copy(script, materials, source_names)
    return script


def _chapter_text(db: Session, ao: str, start: datetime, end: datetime) -> tuple[str, int]:
    material, count = _chapter_material(db, ao, start, end)
    if material["no_material_change"]:
        return f"{material['title']}. No material change.", 0
    return _fallback_chapter(material, _known_source_names(db)), count


def build_episode_script(
    db: Session,
    period_end: datetime | None = None,
) -> tuple[list[dict], str, datetime, datetime, int]:
    """Create the news-first script with one rewrite call and a facts-only fallback."""
    period_end = period_end or datetime.utcnow()
    period_start = period_end - timedelta(hours=24)
    local_day = period_end.replace(tzinfo=ZoneInfo("UTC")).astimezone(
        ZoneInfo(settings.AUDIO_BRIEF_TIMEZONE)
    ).strftime("%A, %-d %B %Y")
    source_names = _known_source_names(db)
    materials = {}
    total_sources = 0
    for ao in AO_ORDER:
        materials[ao], count = _chapter_material(db, ao, period_start, period_end)
        total_sources += count
    try:
        script = _podcast_rewrite(materials, source_names, local_day)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Podcast rewrite unavailable; using current factual leads: %s", exc)
        script = _fallback_script(materials, source_names)
        _validate_podcast_copy(script, materials, source_names)

    opening = f"This is Sentinel, with your morning briefing for {local_day}. " + script["opening"]
    sections = [{"key": "opening", "title": "Opening", "text": opening}]
    transcript_parts = [sections[0]["text"]]
    for ao in AO_ORDER:
        key, title = AO_AUDIO[ao]
        chapter = script[key]
        sections.append({"key": key, "title": title, "text": chapter})
        transcript_parts.append(f"{title.upper()}\n\n{chapter}")
    sections.append({"key": "closing", "title": "Closing", "text": _clean_spoken_text(script["closing"])})
    transcript_parts.append(sections[-1]["text"])
    transcript = "\n\n".join(transcript_parts)
    validate_episode_script(sections, transcript)
    return sections, transcript, period_start, period_end, total_sources


def validate_episode_script(sections: list[dict], transcript: str) -> None:
    keys = [section.get("key") for section in sections]
    if keys != list(PODCAST_KEYS):
        raise ValueError("Audio briefing chapters are missing or out of order")
    if NON_LATIN_SCRIPT.search(transcript or ""):
        raise ValueError("Audio briefing contains untranslated non-English script")
    if PROHIBITED_SPOKEN_LANGUAGE.search(transcript or ""):
        raise ValueError("Audio briefing contains behind-the-scenes language")
    if any(not (section.get("text") or "").strip() for section in sections):
        raise ValueError("Audio briefing contains an empty chapter")
    if len((transcript or "").split()) > 700:
        raise ValueError("Audio briefing exceeds the short-format script ceiling")


def audio_path_for(episode: AudioBrief) -> Path | None:
    if not episode.audio_filename or Path(episode.audio_filename).name != episode.audio_filename:
        return None
    path = (AUDIO_DIR / episode.audio_filename).resolve()
    if path.parent != AUDIO_DIR.resolve() or not path.is_file():
        return None
    return path


def _cleanup_old_episodes(db: Session) -> None:
    cutoff = datetime.utcnow() - timedelta(days=settings.AUDIO_BRIEF_RETENTION_DAYS)
    expired = db.query(AudioBrief).filter(AudioBrief.generated_at < cutoff).all()
    for episode in expired:
        path = audio_path_for(episode)
        if path:
            path.unlink(missing_ok=True)
        elif episode.audio_filename and cloud_storage_enabled():
            delete_audio(episode.audio_filename)
        db.delete(episode)
    if expired:
        db.commit()


def generate_audio_brief(db: Session, period_end: datetime | None = None) -> AudioBrief:
    sections, transcript, period_start, period_end, source_count = build_episode_script(db, period_end)
    # End the read transaction before local synthesis, which may take several
    # minutes, so normal collection writes are never held behind the audio job.
    db.rollback()
    timezone = ZoneInfo(settings.AUDIO_BRIEF_TIMEZONE)
    episode_date = period_end.replace(tzinfo=ZoneInfo("UTC")).astimezone(timezone).date().isoformat()
    title = f"SENTINEL Morning Intelligence Update — {episode_date}"

    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    revision = datetime.utcnow().strftime("%H%M%S")
    final_name = f"sentinel-morning-{episode_date}-{revision}.m4a"
    final_path = AUDIO_DIR / final_name

    with tempfile.TemporaryDirectory(prefix="episode-", dir=AUDIO_DIR) as temp_dir:
        temp_dir_path = Path(temp_dir)
        manifest_path = temp_dir_path / "manifest.json"
        output_path = temp_dir_path / "episode.m4a"
        metadata_path = temp_dir_path / "metadata.json"
        manifest_path.write_text(json.dumps({"sections": sections}), encoding="utf-8")
        python = TTS_PYTHON if TTS_PYTHON.exists() else Path(sys.executable)
        result = subprocess.run(
            [
                str(python), str(TTS_WORKER),
                "--manifest", str(manifest_path),
                "--output", str(output_path),
                "--metadata", str(metadata_path),
                "--voice", settings.AUDIO_BRIEF_VOICE,
                "--fallback-voice", settings.AUDIO_BRIEF_FALLBACK_VOICE,
                "--speed", str(settings.AUDIO_BRIEF_SPEED),
                "--fallback-rate", str(settings.AUDIO_BRIEF_FALLBACK_RATE),
                "--onnx-model", settings.KOKORO_MODEL_PATH,
                "--onnx-voices", settings.KOKORO_VOICES_PATH,
            ],
            cwd=PROJECT_DIR,
            capture_output=True,
            text=True,
            timeout=20 * 60,
            check=False,
        )
        if result.returncode != 0 or not output_path.is_file() or not metadata_path.is_file():
            detail = (result.stderr or result.stdout or "audio worker failed").strip()
            raise RuntimeError(detail[-800:])
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        os.replace(output_path, final_path)

    existing = db.query(AudioBrief).filter(AudioBrief.episode_date == episode_date).first()
    old_path = audio_path_for(existing) if existing else None
    old_object_key = existing.audio_filename if existing and cloud_storage_enabled() else None
    if cloud_storage_enabled():
        upload_audio(final_path, final_name)
    episode = existing or AudioBrief(episode_date=episode_date)
    episode.generated_at = datetime.utcnow()
    episode.period_start = period_start
    episode.period_end = period_end
    episode.title = title
    episode.transcript = transcript
    episode.chapters_json = json.dumps(metadata.get("chapters", []))
    episode.audio_filename = final_name
    episode.mime_type = "audio/mp4"
    episode.duration_seconds = float(metadata["duration_seconds"])
    episode.word_count = len(transcript.split())
    episode.source_article_count = source_count
    episode.voice_engine = metadata.get("engine", "unknown")
    episode.status = "ready"
    episode.last_error = None
    if not existing:
        db.add(episode)
    try:
        db.commit()
        db.refresh(episode)
    except Exception:
        if cloud_storage_enabled():
            try:
                delete_audio(final_name)
            except Exception:  # noqa: BLE001
                logger.exception("Could not remove failed replacement audio object")
        final_path.unlink(missing_ok=True)
        db.rollback()
        raise
    if old_path and old_path != final_path:
        old_path.unlink(missing_ok=True)
    if old_object_key and old_object_key != final_name:
        try:
            delete_audio(old_object_key)
        except Exception:  # noqa: BLE001
            logger.exception("Could not remove replaced audio object %s", old_object_key)
    if cloud_storage_enabled():
        final_path.unlink(missing_ok=True)
    _cleanup_old_episodes(db)
    return episode
