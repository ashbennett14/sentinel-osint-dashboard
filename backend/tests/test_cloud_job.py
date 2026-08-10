from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch
from zoneinfo import ZoneInfo

from scripts.cloud_job import scheduled_morning_is_due


class _Query:
    def __init__(self, episode):
        self.episode = episode

    def filter(self, *args):
        return self

    def first(self):
        return self.episode


class _Db:
    def __init__(self, episode=None):
        self.episode = episode
        self.closed = False

    def query(self, _model):
        return _Query(self.episode)

    def close(self):
        self.closed = True


def _london_time(hour: int) -> datetime:
    return datetime(2026, 8, 10, hour, 15, tzinfo=ZoneInfo("Europe/London"))


def test_scheduled_morning_waits_until_six_local():
    with patch("scripts.cloud_job.datetime") as clock, patch(
        "scripts.cloud_job.SessionLocal"
    ) as session:
        clock.now.return_value = _london_time(5)
        assert scheduled_morning_is_due(False) is False
        session.assert_not_called()


def test_scheduled_morning_runs_late_when_today_is_missing():
    db = _Db()
    with patch("scripts.cloud_job.datetime") as clock, patch(
        "scripts.cloud_job.SessionLocal", return_value=db
    ):
        clock.now.return_value = _london_time(9)
        assert scheduled_morning_is_due(False) is True
    assert db.closed is True


def test_scheduled_morning_skips_when_today_is_ready():
    db = _Db(SimpleNamespace(status="ready"))
    with patch("scripts.cloud_job.datetime") as clock, patch(
        "scripts.cloud_job.SessionLocal", return_value=db
    ):
        clock.now.return_value = _london_time(7)
        assert scheduled_morning_is_due(False) is False
    assert db.closed is True


def test_forced_morning_always_runs_without_database_check():
    with patch("scripts.cloud_job.SessionLocal") as session:
        assert scheduled_morning_is_due(True) is True
        session.assert_not_called()
