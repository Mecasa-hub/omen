#!/usr/bin/env python3
"""OMEN — Database Migration Script.

Creates all database tables from SQLAlchemy ORM models.
Safe to run multiple times (idempotent) — existing tables are skipped.

Usage:
    python scripts/migrate_db.py
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add backend to Python path
BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("migrate_db")


async def migrate() -> None:
    """Create all database tables defined in models.py."""
    from database import Base, engine

    # Import all models so they register with Base.metadata
    import models  # noqa: F401

    logger.info("=" * 60)
    logger.info("  OMEN — Database Migration")
    logger.info("=" * 60)

    # Get list of tables before migration
    from sqlalchemy import inspect

    async with engine.connect() as conn:
        existing_tables = await conn.run_sync(
            lambda sync_conn: inspect(sync_conn).get_table_names()
        )

    if existing_tables:
        logger.info("Existing tables found: %s", ", ".join(sorted(existing_tables)))
    else:
        logger.info("No existing tables found — fresh database.")

    # All tables defined in models
    model_tables = sorted(Base.metadata.tables.keys())
    logger.info("Tables defined in models: %s", ", ".join(model_tables))

    # Create tables (checkfirst=True by default in create_all)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Verify what was created
    async with engine.connect() as conn:
        final_tables = await conn.run_sync(
            lambda sync_conn: inspect(sync_conn).get_table_names()
        )

    new_tables = set(final_tables) - set(existing_tables)
    skipped_tables = set(final_tables) & set(existing_tables)

    if new_tables:
        logger.info("✅ Created tables: %s", ", ".join(sorted(new_tables)))
    if skipped_tables:
        logger.info("⏭️  Skipped (already exist): %s", ", ".join(sorted(skipped_tables)))

    logger.info("")
    logger.info("Migration complete — %d tables total.", len(final_tables))

    # Dispose engine
    await engine.dispose()


def main() -> None:
    """Entry point."""
    try:
        asyncio.run(migrate())
    except KeyboardInterrupt:
        logger.info("Migration interrupted.")
        sys.exit(1)
    except Exception as exc:
        logger.error("Migration failed: %s", exc, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
