"""Database backend factory."""

import logging
from src.config.settings import DB_BACKEND, SQLITE_DB_PATH, SUPABASE_URL, SUPABASE_KEY

logger = logging.getLogger(__name__)


def create_queries():
    """Create the appropriate database queries backend."""
    if DB_BACKEND == "sqlite":
        from src.database.sqlite_queries import SQLiteQueries
        logger.info("Using SQLite backend: %s", SQLITE_DB_PATH)
        return SQLiteQueries(SQLITE_DB_PATH)
    else:
        from src.database.client import SupabaseClient
        from src.database.queries import DatabaseQueries
        logger.info("Using Supabase backend")
        db = SupabaseClient(SUPABASE_URL, SUPABASE_KEY)
        return DatabaseQueries(db)
