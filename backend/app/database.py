import logging

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.pool import NullPool
from sqlalchemy.orm import sessionmaker, declarative_base

from app.config import settings

logger = logging.getLogger("sentinel.database")

def _normalise_database_url(value: str) -> str:
    if value.startswith("postgres://"):
        return "postgresql+psycopg://" + value[len("postgres://"):]
    if value.startswith("postgresql://"):
        return "postgresql+psycopg://" + value[len("postgresql://"):]
    return value


DATABASE_URL = _normalise_database_url(settings.DATABASE_URL)
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine_options = {"connect_args": connect_args, "pool_pre_ping": True}
if settings.HOSTED_MODE and not DATABASE_URL.startswith("sqlite"):
    engine_options["poolclass"] = NullPool
engine = create_engine(DATABASE_URL, **engine_options)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _run_auto_migrations():
    """
    Lightweight additive-only migration: for any table that already exists,
    add any column present in the current models but missing from the
    actual database. This is deliberately simple (no renames, no drops, no
    type changes) — good enough for a single-user local app to survive
    code updates without ever needing to delete the database.
    """
    if engine.dialect.name != "sqlite":
        return
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    reset_processed_for_clustering = False

    with engine.begin() as conn:
        for table in Base.metadata.sorted_tables:
            if table.name not in existing_tables:
                continue  # brand new table — create_all() already handled it

            existing_cols = {c["name"] for c in inspector.get_columns(table.name)}
            for col in table.columns:
                if col.name in existing_cols:
                    continue
                col_type = col.type.compile(engine.dialect)
                ddl = f"ALTER TABLE {table.name} ADD COLUMN {col.name} {col_type}"
                conn.execute(text(ddl))
                logger.info("Migration: added column %s.%s", table.name, col.name)
                if table.name == "articles" and col.name in ("cluster_key", "is_cluster_primary"):
                    reset_processed_for_clustering = True

        if reset_processed_for_clustering:
            # Existing articles predate deduplication — let them run through
            # classification again so they get clustered like everything else.
            conn.execute(text("UPDATE articles SET processed = 0 WHERE cluster_key IS NULL"))
            logger.info("Migration: queued existing articles for reclassification/clustering")


def init_db():
    from app import models  # noqa: ensures models are registered on Base
    Base.metadata.create_all(bind=engine)
    try:
        _run_auto_migrations()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Auto-migration step failed (app will still start): %s", exc)
