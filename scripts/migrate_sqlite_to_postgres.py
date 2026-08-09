#!/usr/bin/env python3
"""One-time, parity-checked SQLite to Postgres/Supabase migration."""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

from sqlalchemy import Boolean, DateTime, create_engine, func, select, text

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.database import Base  # noqa: E402
from app import models  # noqa: E402,F401
from app.storage import upload_audio  # noqa: E402

TABLES = ("sources", "articles", "synopses", "briefs", "audio_briefs", "system_status")


def normalise_url(value: str) -> str:
    if value.startswith("postgres://"):
        return "postgresql+psycopg://" + value[len("postgres://"):]
    if value.startswith("postgresql://"):
        return "postgresql+psycopg://" + value[len("postgresql://"):]
    return value


def convert_row(row: sqlite3.Row, table) -> dict:
    result = dict(row)
    for column in table.columns:
        value = result.get(column.name)
        if value is None:
            continue
        if isinstance(column.type, Boolean):
            result[column.name] = bool(value)
        elif isinstance(column.type, DateTime) and isinstance(value, str):
            result[column.name] = datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sqlite", default=str(ROOT / "backend" / "sentinel.db"))
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL", ""))
    parser.add_argument("--audio-dir", default=str(ROOT / "backend" / "generated" / "audio"))
    args = parser.parse_args()
    if not args.database_url or not args.database_url.startswith(("postgres://", "postgresql://")):
        parser.error("--database-url must be a Postgres connection URL")

    sqlite_path = Path(args.sqlite).resolve()
    if not sqlite_path.is_file():
        parser.error(f"SQLite database not found: {sqlite_path}")
    backup = sqlite_path.with_name(f"{sqlite_path.stem}.migration-{datetime.now():%Y%m%d-%H%M%S}.bak")
    shutil.copy2(sqlite_path, backup)
    print(f"Created rollback backup: {backup}")

    target = create_engine(normalise_url(args.database_url), pool_pre_ping=True)
    Base.metadata.create_all(target)
    with target.connect() as connection:
        occupied = sum(connection.execute(select(func.count()).select_from(Base.metadata.tables[name])).scalar_one() for name in TABLES)
    if occupied:
        raise RuntimeError("Target database is not empty; migration aborted without changing it")

    source = sqlite3.connect(sqlite_path)
    source.row_factory = sqlite3.Row
    expected = {}
    with target.begin() as connection:
        for name in TABLES:
            table = Base.metadata.tables[name]
            rows = source.execute(f'SELECT * FROM "{name}" ORDER BY id').fetchall()
            expected[name] = len(rows)
            for offset in range(0, len(rows), 500):
                connection.execute(table.insert(), [convert_row(row, table) for row in rows[offset:offset + 500]])
            if rows:
                connection.execute(text(
                    "SELECT setval(pg_get_serial_sequence(:table, 'id'), "
                    "COALESCE((SELECT MAX(id) FROM \"" + name + "\"), 1), true)"
                ), {"table": name})
    source.close()

    audio_dir = Path(args.audio_dir).resolve()
    audio_rows = sqlite3.connect(sqlite_path).execute(
        "SELECT audio_filename FROM audio_briefs WHERE status='ready' AND audio_filename IS NOT NULL"
    ).fetchall()
    for (filename,) in audio_rows:
        path = (audio_dir / Path(filename).name).resolve()
        if path.parent == audio_dir and path.is_file():
            upload_audio(path, filename)
            print(f"Uploaded {filename} ({hashlib.sha256(path.read_bytes()).hexdigest()[:16]}…)")

    with target.connect() as connection:
        actual = {
            name: connection.execute(select(func.count()).select_from(Base.metadata.tables[name])).scalar_one()
            for name in TABLES
        }
    if actual != expected:
        raise RuntimeError(f"Migration parity failed: expected={expected}, actual={actual}")
    print(f"Migration verified: {actual}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
