"""Interfaces shared by metadata backends."""

from datetime import datetime
from typing import Protocol
from uuid import UUID

from urbanflow.database.models import IngestionRun, SourceRelease


class MetadataRepository(Protocol):
    """Persistence operations required by source-ingestion workflows."""

    def begin_run(self, run: IngestionRun) -> None:
        """Insert the initial record for a new ingestion attempt."""

    def update_attempt(self, run_id: UUID, attempts: int) -> None:
        """Record the current HTTP attempt count."""

    def complete_run(self, run: IngestionRun, *, unchanged: bool = False) -> None:
        """Store a successful attempt and its source-release record."""

    def fail_run(
        self, run_id: UUID, *, completed_at_utc: datetime, attempts: int, error: str
    ) -> None:
        """Mark an attempt failed while retaining its error and retry count."""

    def latest_release(self, source_id: str, source_period: str) -> SourceRelease | None:
        """Return the most recently retrieved release for a source period."""

    def get_run(self, run_id: UUID) -> IngestionRun:
        """Return one persisted ingestion attempt."""
