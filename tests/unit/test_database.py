"""Check PostgreSQL adapter setup and metadata-model validation."""

from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import pytest

from urbanflow.database.models import IngestionRun, SourceRelease
from urbanflow.database.postgres import PostgresMetadataAdapter


class FakeCursor:
    """Minimal cursor response used to check adapter SQL calls."""

    rowcount = 1

    def fetchone(self):
        return None


class FakeConnection:
    """Capture SQL statements without requiring a running database service."""

    def __init__(self) -> None:
        self.statements: list[tuple[str, tuple | None]] = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return None

    def execute(self, query: str, params: tuple | None = None) -> FakeCursor:
        self.statements.append((query, params))
        return FakeCursor()


def test_postgres_adapter_creates_typed_schema_and_uses_parameterized_queries(monkeypatch):
    connections: list[FakeConnection] = []
    connect_calls: list[tuple[tuple, dict]] = []

    def connect(*args, **kwargs):
        connect_calls.append((args, kwargs))
        connection = FakeConnection()
        connections.append(connection)
        return connection

    monkeypatch.setattr("urbanflow.database.postgres.psycopg.connect", connect)
    adapter = PostgresMetadataAdapter("postgresql://user@localhost/db")

    ddl = "\n".join(query for query, _params in connections[0].statements)
    assert "TIMESTAMPTZ" in ddl
    assert "JSONB" in ddl
    assert "source_releases" in ddl
    assert connect_calls[0][1]["application_name"] == "urbanflow-ingestion"
    assert connect_calls[0][1]["connect_timeout"] == 10

    run = IngestionRun(
        run_id=uuid4(),
        source_id="nyc_tlc.yellow_taxi",
        source_period="2024-01",
        source_url="https://example.test/file.parquet?x=1' OR 'x'='x",
        status="downloading",
        started_at_utc=datetime.now(UTC),
    )
    adapter.begin_run(run)
    query, params = connections[1].statements[0]
    assert "%s" in query
    assert run.source_url in params


@pytest.mark.parametrize(
    ("timestamp", "message"),
    [
        (datetime(2024, 1, 1), "timezone-aware UTC"),
        (datetime(2024, 1, 1, tzinfo=timezone(timedelta(hours=3))), "timezone-aware UTC"),
    ],
)
def test_ingestion_run_requires_a_utc_timestamp(timestamp, message):
    with pytest.raises(ValueError, match=message):
        IngestionRun(
            run_id=uuid4(),
            source_id="nyc_tlc.yellow_taxi",
            source_period="2024-01",
            source_url="https://example.test/file.parquet",
            status="downloading",
            started_at_utc=timestamp,
        )


def test_source_release_requires_sha256_and_utc_timestamp():
    with pytest.raises(ValueError, match="sha256"):
        SourceRelease(
            release_id="release",
            source_id="nyc_tlc.yellow_taxi",
            source_period="2024-01",
            source_url="https://example.test/file.parquet",
            retrieved_at_utc=datetime.now(UTC),
            file_path=Path("file.parquet"),
            byte_count=1,
            sha256="not-a-checksum",
            etag=None,
            source_last_modified=None,
        )
