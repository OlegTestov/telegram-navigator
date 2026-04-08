"""Supabase client wrapper with connection management."""

import logging
from typing import Optional

from supabase import Client, create_client
from tenacity import retry, stop_after_attempt, wait_exponential

from src.utils.errors import DatabaseError

logger = logging.getLogger(__name__)


class SupabaseClient:
    """Wrapper for Supabase client with retry logic."""

    def __init__(self, url: str, key: str):
        self.url = url
        self.key = key
        self._client: Optional[Client] = None

    @property
    def client(self) -> Client:
        if self._client is None:
            try:
                self._client = create_client(self.url, self.key)
            except Exception as e:
                logger.error("Failed to create Supabase client: %s", e)
                raise DatabaseError(f"Database connection failed: {e}") from e
        return self._client

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    def execute(self, operation):
        """Execute database operation with retry logic."""
        try:
            return operation()
        except Exception as e:
            logger.error("Database operation failed: %s", e)
            raise DatabaseError(f"Database operation failed: {e}") from e
