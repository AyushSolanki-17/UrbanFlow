"""Typed metadata models shared by database adapters."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Literal
from uuid import UUID

RunStatus = Literal["downloading", "succeeded", "unchanged", "failed"]


@dataclass(frozen=True)
class IngestionRun:
    """Metadata describing one attempt to acquire a source object.

    Attributes:
        run_id: Unique identifier for this attempt.
        source_id: Stable identifier for the logical source.
        source_period: Source coverage period, such as ``2024-01``.
        source_url: URL used to retrieve the source object.
        status: State of the ingestion attempt.
        started_at_utc: Time the attempt started, as an aware UTC datetime.
        completed_at_utc: Time the attempt completed, when available.
        file_path: Local immutable release path, when available.
        byte_count: Number of bytes retrieved, when available.
        sha256: Content checksum, when available.
        etag: HTTP entity tag, if supplied by the server.
        source_last_modified: HTTP Last-Modified header, if supplied.
        attempts: Number of HTTP requests made.
        error_message: Failure detail, if the run failed.
    """

    run_id: UUID
    source_id: str
    source_period: str
    source_url: str
    status: RunStatus
    started_at_utc: datetime
    completed_at_utc: datetime | None = None
    file_path: Path | None = None
    byte_count: int | None = None
    sha256: str | None = None
    etag: str | None = None
    source_last_modified: str | None = None
    attempts: int = 0
    error_message: str | None = None

    def __post_init__(self) -> None:
        """Require timestamps stored under UTC fields to be timezone-aware UTC."""
        for value in (self.started_at_utc, self.completed_at_utc):
            if value is not None and (value.tzinfo is None or value.utcoffset() != timedelta(0)):
                raise ValueError("UTC timestamp fields require timezone-aware UTC datetimes")
        if self.byte_count is not None and self.byte_count < 0:
            raise ValueError("byte_count must be non-negative")
        if self.attempts < 0:
            raise ValueError("attempts must be non-negative")


@dataclass(frozen=True)
class SourceRelease:
    """Immutable reference to one downloaded content version.

    Attributes:
        release_id: Stable source-period and checksum identity.
        source_id: Stable identifier for the logical source.
        source_period: Source coverage period, such as ``2024-01``.
        source_url: URL used to retrieve the source object.
        retrieved_at_utc: Retrieval completion time as an aware UTC datetime.
        file_path: Local path containing the source object.
        byte_count: Number of bytes in the downloaded source object.
        sha256: SHA-256 checksum of the complete source object.
        etag: HTTP entity tag, if supplied by the server.
        source_last_modified: HTTP Last-Modified header, if supplied.
        row_count: Parsed source row count, if a later validation stage records it.
        schema_json: Parsed source schema, if a later validation stage records it.
    """

    release_id: str
    source_id: str
    source_period: str
    source_url: str
    retrieved_at_utc: datetime
    file_path: Path
    byte_count: int
    sha256: str
    etag: str | None
    source_last_modified: str | None
    row_count: int | None = None
    schema_json: str | None = None

    def __post_init__(self) -> None:
        """Validate invariants for an immutable source release."""
        if self.retrieved_at_utc.tzinfo is None or self.retrieved_at_utc.utcoffset() != timedelta(
            0
        ):
            raise ValueError("retrieved_at_utc requires a timezone-aware UTC datetime")
        if self.byte_count < 0:
            raise ValueError("byte_count must be non-negative")
        if self.row_count is not None and self.row_count < 0:
            raise ValueError("row_count must be non-negative")
        if len(self.sha256) != 64 or any(char not in "0123456789abcdef" for char in self.sha256):
            raise ValueError("sha256 must be a lowercase 64-character hexadecimal digest")
