import unittest
from datetime import datetime, timedelta
from pathlib import Path
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.analysis.audio_brief import (
    AO_ORDER,
    _cleanup_old_episodes,
    _articles_for_period,
    _brief_section,
    _development_text,
    _chapter_text,
    _validate_podcast_copy,
    _augment_short_chapters,
    _podcast_rewrite,
    audio_path_for,
    validate_episode_script,
)
from app.database import Base
from app.models import AudioBrief


class _Query:
    def __init__(self, rows):
        self.rows = rows

    def filter(self, *args):
        return self

    def order_by(self, *args):
        return self

    def limit(self, _limit):
        return self

    def all(self):
        return self.rows


class _Db:
    def __init__(self, rows):
        self.rows = rows

    def query(self, _model):
        return _Query(self.rows)


class AudioBriefTests(unittest.TestCase):
    def test_required_ao_order_is_stable(self):
        self.assertEqual(AO_ORDER, ("AO_HIGH_NORTH", "AO_EUROPE", "AO_BALKANS", "AO_LEVANT"))

    def test_assessment_and_outlook_sections_are_extracted(self):
        content = "## 4. ASSESSMENT\nMeasured assessment.\n## 5. OUTLOOK & INDICATORS\nWatch indicators.\n## 6. GAPS\nGap."
        self.assertEqual(_brief_section(content, 4), "Measured assessment.")
        self.assertEqual(_brief_section(content, 5), "Watch indicators.")

    def test_article_priority_prefers_severity_then_reliability(self):
        now = datetime.utcnow()
        official = SimpleNamespace(
            severity=4, published_at=now, source=SimpleNamespace(reliability="official")
        )
        unverified = SimpleNamespace(
            severity=5, published_at=now - timedelta(minutes=1),
            source=SimpleNamespace(reliability="unverified"),
        )
        result = _articles_for_period(
            _Db([official, unverified]), "AO_EUROPE", now - timedelta(days=1), now
        )
        self.assertEqual(result, [unverified, official])

    def test_script_validator_accepts_complete_target_length(self):
        sections = [
            {"key": key, "text": "update " * 180}
            for key in ("opening", "high-north", "eastern-europe", "balkans", "levant", "closing")
        ]
        validate_episode_script(sections, "update " * 900)

    def test_script_validator_rejects_wrong_chapter_order(self):
        sections = [
            {"key": key, "text": "update " * 180}
            for key in ("opening", "eastern-europe", "high-north", "balkans", "levant", "closing")
        ]
        with self.assertRaisesRegex(ValueError, "out of order"):
            validate_episode_script(sections, "update " * 900)

    def test_script_validator_rejects_methodology_language(self):
        sections = [
            {"key": key, "text": "Natural spoken update."}
            for key in ("opening", "high-north", "eastern-europe", "balkans", "levant", "closing")
        ]
        with self.assertRaisesRegex(ValueError, "behind-the-scenes"):
            validate_episode_script(sections, "The source reporting has low confidence. " * 100)

    def test_podcast_copy_rejects_named_publishers(self):
        script = {
            key: "A calm and natural regional update."
            for key in ("opening", "high-north", "eastern-europe", "balkans", "levant", "closing")
        }
        script["balkans"] = "Example News describes increased tension."
        materials = {
            ao: {"no_material_change": False}
            for ao in AO_ORDER
        }
        with self.assertRaisesRegex(ValueError, "publisher"):
            _validate_podcast_copy(script, materials, ["Example News"])

    def test_short_active_chapter_is_expanded_without_methodology(self):
        script = {key: "A natural update." for key in (
            "opening", "high-north", "eastern-europe", "balkans", "levant", "closing"
        )}
        materials = {}
        for ao in AO_ORDER:
            materials[ao] = {
                "ao": ao,
                "title": "Regional area",
                "no_material_change": False,
                "developments": [
                    {"title": f"Military activity continued near the border sector number {i}.", "summary": ""}
                    for i in range(4)
                ],
                "situation": "Tension remains elevated across several border districts.",
                "assessment": "The activity may place additional pressure on neighbouring authorities.",
                "outlook": "Further movement is possible during the next several days.",
            }
        _augment_short_chapters(script, materials, [])
        self.assertGreater(len(script["high-north"].split()), 40)
        self.assertNotIn("source", script["high-north"].lower())

    def test_podcast_rewrite_uses_one_model_call(self):
        keys = ("opening", "high-north", "eastern-europe", "balkans", "levant", "closing")
        response = {key: "A calm natural update for the listener." for key in keys}
        materials = {
            ao: {
                "ao": ao,
                "title": "Regional area",
                "no_material_change": True,
                "developments": [],
                "situation": "",
                "assessment": "",
                "outlook": "",
            }
            for ao in AO_ORDER
        }
        with patch("app.analysis.audio_brief.complete", return_value=__import__("json").dumps(response)) as model:
            script = _podcast_rewrite(materials, [], "Sunday, 9 August 2026")
        model.assert_called_once()
        self.assertEqual(script["balkans"], "The Balkans. No material change.")

    def test_spoken_developments_do_not_name_sources(self):
        article = SimpleNamespace(
            title="Military exercise begins in Serbia",
            category="exercise",
            country="Serbia",
            ao="AO_BALKANS",
            source=SimpleNamespace(name="Example News", reliability="established_media"),
        )
        spoken = _development_text([article])
        self.assertIn("Military exercise begins in Serbia", spoken)
        self.assertNotIn("Example News", spoken)
        self.assertNotIn("source tier", spoken)

    def test_empty_ao_is_reported_as_no_material_change(self):
        now = datetime.utcnow()
        with patch("app.analysis.audio_brief._articles_for_period", return_value=[]):
            spoken, count = _chapter_text(_Db([]), "AO_BALKANS", now - timedelta(days=1), now)
        self.assertEqual(spoken, "The Balkans. No material change.")
        self.assertEqual(count, 0)

    def test_audio_path_rejects_traversal(self):
        self.assertIsNone(audio_path_for(SimpleNamespace(audio_filename="../episode.m4a")))

    def test_retention_removes_expired_metadata_and_audio(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        session = sessionmaker(bind=engine)()
        with tempfile.TemporaryDirectory() as temp_dir:
            audio_dir = Path(temp_dir)
            audio_file = audio_dir / "expired.m4a"
            audio_file.write_bytes(b"expired")
            session.add(AudioBrief(
                episode_date="2026-01-01",
                generated_at=datetime.utcnow() - timedelta(days=31),
                period_start=datetime.utcnow() - timedelta(days=32),
                period_end=datetime.utcnow() - timedelta(days=31),
                title="Expired",
                transcript="Expired transcript",
                chapters_json="[]",
                audio_filename=audio_file.name,
                mime_type="audio/mp4",
                status="ready",
            ))
            session.commit()
            with patch("app.analysis.audio_brief.AUDIO_DIR", audio_dir):
                _cleanup_old_episodes(session)
            self.assertFalse(audio_file.exists())
            self.assertEqual(session.query(AudioBrief).count(), 0)
        session.close()


if __name__ == "__main__":
    unittest.main()
