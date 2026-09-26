"""PostgreSQL metadata repository for ingestion attempts and source releases."""

import json
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID

import psycopg
from psycopg.rows import dict_row

from urbanflow.database.models import IngestionRun, SourceRelease

_SCHEMA_VERSION = 1


class PostgresMetadataAdapter:
    """Persist source provenance and ingestion history in PostgreSQL.

    Args:
        conninfo: PostgreSQL connection URI or libpq connection string.
        connect_timeout_seconds: Connection timeout for each database session.
    """

    def __init__(self, conninfo: str, *, connect_timeout_seconds: int = 10) -> None:
        self._conninfo = conninfo
        self._connect_timeout_seconds = connect_timeout_seconds
        self._initialize()

    @contextmanager
    def _connect(self) -> Iterator[psycopg.Connection[dict[str, Any]]]:
        """Open a transaction and close its connection after use."""
        with psycopg.connect(
            self._conninfo,
            connect_timeout=self._connect_timeout_seconds,
            application_name="urbanflow-ingestion",
            row_factory=dict_row,
        ) as connection:
            yield connection

    def _initialize(self) -> None:
        """Create the versioned metadata schema when it is first required."""
        with self._connect() as connection:
            connection.execute(
                """CREATE TABLE IF NOT EXISTS urbanflow_schema_migrations (
                    version INTEGER PRIMARY KEY,
                    applied_at_utc TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
                )"""
            )
            connection.execute(
                """CREATE TABLE IF NOT EXISTS ingestion_runs (
                    run_id UUID PRIMARY KEY,
                    source_id TEXT NOT NULL,
                    source_period TEXT NOT NULL,
                    source_url TEXT NOT NULL,
                    status TEXT NOT NULL CHECK (status IN (
                        'downloading', 'succeeded', 'unchanged', 'failed'
                    )),
                    started_at_utc TIMESTAMPTZ NOT NULL,
                    completed_at_utc TIMESTAMPTZ,
                    file_path TEXT,
                    byte_count BIGINT CHECK (byte_count IS NULL OR byte_count >= 0),
                    sha256 CHAR(64),
                    etag TEXT,
                    source_last_modified TEXT,
                    attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0),
                    error_message TEXT
                )"""
            )
            connection.execute(
                """CREATE INDEX IF NOT EXISTS ingestion_runs_source_period
                   ON ingestion_runs (source_id, source_period, started_at_utc DESC)"""
            )
            connection.execute(
                """CREATE TABLE IF NOT EXISTS source_releases (
                    release_id TEXT PRIMARY KEY,
                    source_id TEXT NOT NULL,
                    source_period TEXT NOT NULL,
                    source_url TEXT NOT NULL,
                    retrieved_at_utc TIMESTAMPTZ NOT NULL,
                    file_path TEXT NOT NULL,
                    byte_count BIGINT NOT NULL CHECK (byte_count >= 0),
                    sha256 CHAR(64) NOT NULL,
                    etag TEXT,
                    source_last_modified TEXT,
                    row_count BIGINT CHECK (row_count IS NULL OR row_count >= 0),
                    schema_json JSONB,
                    UNIQUE (source_id, source_period, sha256)
                )"""
            )
            connection.execute(
                """CREATE INDEX IF NOT EXISTS source_releases_source_period
                   ON source_releases (source_id, source_period, retrieved_at_utc DESC)"""
            )
            connection.execute(
                """INSERT INTO urbanflow_schema_migrations (version)
                   VALUES (%s) ON CONFLICT (version) DO NOTHING""",
                (_SCHEMA_VERSION,),
            )

    def begin_run(self, run: IngestionRun) -> None:
        """Insert the initial record for a new ingestion attempt."""
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO ingestion_runs
                   (run_id, source_id, source_period, source_url, status, started_at_utc)
                   VALUES (%s, %s, %s, %s, 'downloading', %s)""",
                (run.run_id, run.source_id, run.source_period, run.source_url, run.started_at_utc),
            )

    def update_attempt(self, run_id: UUID, attempts: int) -> None:
        """Record the current HTTP attempt count."""
        with self._connect() as connection:
            connection.execute(
                "UPDATE ingestion_runs SET attempts = %s WHERE run_id = %s",
                (attempts, run_id),
            )

    def complete_run(self, run: IngestionRun, *, unchanged: bool = False) -> None:
        """Commit a successful run and, when new, its immutable release record."""
        if run.file_path is None or run.byte_count is None or run.sha256 is None:
            raise ValueError("successful runs require file_path, byte_count, and sha256")
        if run.completed_at_utc is None:
            raise ValueError("successful runs require completed_at_utc")
        release_id = f"{run.source_id}:{run.source_period}:sha256:{run.sha256}"
        with self._connect() as connection:
            if not unchanged:
                connection.execute(
                    """INSERT INTO source_releases
                       (release_id, source_id, source_period, source_url, retrieved_at_utc,
                        file_path, byte_count, sha256, etag, source_last_modified)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                       ON CONFLICT (source_id, source_period, sha256) DO NOTHING""",
                    (
                        release_id,
                        run.source_id,
                        run.source_period,
                        run.source_url,
                        run.completed_at_utc,
                        str(run.file_path),
                        run.byte_count,
                        run.sha256,
                        run.etag,
                        run.source_last_modified,
                    ),
                )
            cursor = connection.execute(
                """UPDATE ingestion_runs SET status = %s, completed_at_utc = %s,
                   file_path = %s, byte_count = %s, sha256 = %s, etag = %s,
                   source_last_modified = %s, attempts = %s WHERE run_id = %s""",
                (
                    "unchanged" if unchanged else "succeeded",
                    run.completed_at_utc,
                    str(run.file_path),
                    run.byte_count,
                    run.sha256,
                    run.etag,
                    run.source_last_modified,
                    run.attempts,
                    run.run_id,
                ),
            )
            if cursor.rowcount != 1:
                raise KeyError(f"unknown ingestion run: {run.run_id}")

    def fail_run(
        self, run_id: UUID, *, completed_at_utc: datetime, attempts: int, error: str
    ) -> None:
        """Mark an attempt failed while retaining its error and retry count."""
        with self._connect() as connection:
            cursor = connection.execute(
                """UPDATE ingestion_runs SET status = 'failed', completed_at_utc = %s,
                   attempts = %s, error_message = %s WHERE run_id = %s""",
                (completed_at_utc, attempts, error[:2000], run_id),
            )
            if cursor.rowcount != 1:
                raise KeyError(f"unknown ingestion run: {run_id}")

    def latest_release(self, source_id: str, source_period: str) -> SourceRelease | None:
        """Return the release from the latest successful source observation."""
        with self._connect() as connection:
            row = connection.execute(
                """SELECT release.* FROM ingestion_runs AS run
                   JOIN source_releases AS release
                     ON release.source_id = run.source_id
                    AND release.source_period = run.source_period
                    AND release.sha256 = run.sha256
                   WHERE run.source_id = %s AND run.source_period = %s
                     AND run.status = 'succeeded'
                   ORDER BY run.completed_at_utc DESC, run.run_id DESC LIMIT 1""",
                (source_id, source_period),
            ).fetchone()
        return _source_release_from_row(row) if row is not None else None

    def get_run(self, run_id: UUID) -> IngestionRun:
        """Return one persisted ingestion attempt."""
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM ingestion_runs WHERE run_id = %s", (run_id,)
            ).fetchone()
        if row is None:
            raise KeyError(f"unknown ingestion run: {run_id}")
        return _ingestion_run_from_row(row)


def _source_release_from_row(row: dict[str, Any]) -> SourceRelease:
    """Convert a PostgreSQL row into a typed source-release model."""
    return SourceRelease(
        release_id=row["release_id"],
        source_id=row["source_id"],
        source_period=row["source_period"],
        source_url=row["source_url"],
        retrieved_at_utc=row["retrieved_at_utc"],
        file_path=Path(row["file_path"]),
        byte_count=row["byte_count"],
        sha256=row["sha256"].strip(),
        etag=row["etag"],
        source_last_modified=row["source_last_modified"],
        row_count=row["row_count"],
        schema_json=(
            json.dumps(row["schema_json"], sort_keys=True)
            if row["schema_json"] is not None
            else None
        ),
    )


def _ingestion_run_from_row(row: dict[str, Any]) -> IngestionRun:
    """Convert a PostgreSQL row into a typed ingestion-run model."""
    return IngestionRun(
        run_id=row["run_id"],
        source_id=row["source_id"],
        source_period=row["source_period"],
        source_url=row["source_url"],
        status=row["status"],
        started_at_utc=row["started_at_utc"],
        completed_at_utc=row["completed_at_utc"],
        file_path=Path(row["file_path"]) if row["file_path"] is not None else None,
        byte_count=row["byte_count"],
        sha256=row["sha256"].strip() if row["sha256"] is not None else None,
        etag=row["etag"],
        source_last_modified=row["source_last_modified"],
        attempts=row["attempts"],
        error_message=row["error_message"],
    )
