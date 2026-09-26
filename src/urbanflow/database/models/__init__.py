"""Typed data models for metadata persistence."""

from urbanflow.database.models.ingestion_run import IngestionRun, RunStatus
from urbanflow.database.models.source_release import SourceRelease

__all__ = ["IngestionRun", "RunStatus", "SourceRelease"]
