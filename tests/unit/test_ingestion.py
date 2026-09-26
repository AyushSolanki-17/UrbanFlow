"""Exercise deterministic boundaries of the Yellow Taxi downloader."""

import hashlib
import io
import json
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import URLError
from uuid import UUID

import pytest

from urbanflow.database.models import IngestionRun, SourceRelease
from urbanflow.ingestion.sources.nyc_taxi import SOURCE_URL_TEMPLATE, download_yellow_taxi


class FakeMetadataRepository:
    """In-memory metadata implementation for isolated downloader tests."""

    def __init__(self) -> None:
        self.runs: dict[UUID, IngestionRun] = {}
        self.releases: list[SourceRelease] = []

    def begin_run(self, run: IngestionRun) -> None:
        self.runs[run.run_id] = run

    def update_attempt(self, run_id: UUID, attempts: int) -> None:
        run = self.runs[run_id]
        self.runs[run_id] = IngestionRun(**{**run.__dict__, "attempts": attempts})

    def complete_run(self, run: IngestionRun, *, unchanged: bool = False) -> None:
        self.runs[run.run_id] = run
        if not unchanged:
            release_id = f"{run.source_id}:{run.source_period}:sha256:{run.sha256}"
            if not any(
                release.source_id == run.source_id
                and release.source_period == run.source_period
                and release.sha256 == run.sha256
                for release in self.releases
            ):
                self.releases.append(
                    SourceRelease(
                        release_id=release_id,
                        source_id=run.source_id,
                        source_period=run.source_period,
                        source_url=run.source_url,
                        retrieved_at_utc=run.completed_at_utc,
                        file_path=run.file_path,
                        byte_count=run.byte_count,
                        sha256=run.sha256,
                        etag=run.etag,
                        source_last_modified=run.source_last_modified,
                    )
                )

    def fail_run(
        self, run_id: UUID, *, completed_at_utc: datetime, attempts: int, error: str
    ) -> None:
        run = self.runs[run_id]
        self.runs[run_id] = IngestionRun(
            **{
                **run.__dict__,
                "status": "failed",
                "completed_at_utc": completed_at_utc,
                "attempts": attempts,
                "error_message": error,
            }
        )

    def latest_release(self, source_id: str, source_period: str) -> SourceRelease | None:
        matches = [
            run
            for run in self.runs.values()
            if run.source_id == source_id
            and run.source_period == source_period
            and run.status == "succeeded"
        ]
        if not matches:
            return None
        latest = max(matches, key=lambda run: (run.completed_at_utc, run.run_id))
        return next(
            release
            for release in self.releases
            if release.source_id == latest.source_id
            and release.source_period == latest.source_period
            and release.sha256 == latest.sha256
        )

    def get_run(self, run_id: UUID) -> IngestionRun:
        return self.runs[run_id]


class FakeResponse(io.BytesIO):
    """Small HTTP response double with headers used by the downloader."""

    def __init__(self, body: bytes, headers: dict[str, str] | None = None):
        super().__init__(body)
        self.headers = headers or {"Content-Length": str(len(body)), "ETag": '"fixture"'}


def fake_urlopen_for(body: bytes, calls: list[tuple[str, float]]):
    """Return an opener that captures requests and yields the supplied body."""

    def urlopen(request, timeout):
        calls.append((request.full_url, timeout))
        return FakeResponse(body)

    return urlopen


def test_download_records_release_and_repeat_is_unchanged(tmp_path):
    body = b"PAR1fixture-dataPAR1"
    calls: list[tuple[str, float]] = []
    store = FakeMetadataRepository()

    first = download_yellow_taxi(
        "2024-01",
        data_dir=tmp_path / "data",
        metadata=store,
        urlopen=fake_urlopen_for(body, calls),
        sleep=lambda _: None,
    )

    assert first["status"] == "succeeded"
    assert first["source_url"] == SOURCE_URL_TEMPLATE.format(period="2024-01")
    assert first["byte_count"] == len(body)
    assert first["sha256"] == hashlib.sha256(body).hexdigest()
    assert first["attempts"] == 1
    assert json.loads(json.dumps(first))["file_path"] == first["file_path"]
    assert first["started_at_utc"].endswith("Z")
    release_path = Path(first["file_path"])
    assert release_path.read_bytes() == body
    assert "period=2024-01" in str(release_path)
    assert "release=sha256-" + str(first["sha256"]) in str(release_path)

    second = download_yellow_taxi(
        "2024-01",
        data_dir=tmp_path / "data",
        metadata=store,
        urlopen=lambda *_args, **_kwargs: pytest.fail("unchanged release should not be fetched"),
    )

    assert second["status"] == "unchanged"
    assert second["sha256"] == first["sha256"]
    assert len(calls) == 1
    assert store.get_run(UUID(str(first["run_id"]))).status == "succeeded"
    assert store.get_run(UUID(str(second["run_id"]))).status == "unchanged"
    assert store.latest_release("nyc_tlc.yellow_taxi", "2024-01").sha256 == first["sha256"]


def test_refresh_preserves_corrected_release_as_new_content(tmp_path):
    store = FakeMetadataRepository()
    original = b"PAR1originalPAR1"
    correction = b"PAR1correctedPAR1"
    first = download_yellow_taxi(
        "2024-01",
        data_dir=tmp_path / "data",
        metadata=store,
        urlopen=fake_urlopen_for(original, []),
        sleep=lambda _: None,
    )
    second = download_yellow_taxi(
        "2024-01",
        data_dir=tmp_path / "data",
        metadata=store,
        refresh=True,
        urlopen=fake_urlopen_for(correction, []),
        sleep=lambda _: None,
    )

    assert first["sha256"] != second["sha256"]
    assert Path(first["file_path"]).read_bytes() == original
    assert Path(second["file_path"]).read_bytes() == correction
    assert store.latest_release("nyc_tlc.yellow_taxi", "2024-01").sha256 == second["sha256"]

    restored = download_yellow_taxi(
        "2024-01",
        data_dir=tmp_path / "data",
        metadata=store,
        refresh=True,
        urlopen=fake_urlopen_for(original, []),
        sleep=lambda _: None,
    )
    assert restored["sha256"] == first["sha256"]
    assert store.latest_release("nyc_tlc.yellow_taxi", "2024-01").sha256 == first["sha256"]

    unchanged = download_yellow_taxi(
        "2024-01",
        data_dir=tmp_path / "data",
        metadata=store,
        urlopen=lambda *_args, **_kwargs: pytest.fail("restored release should not be fetched"),
    )
    assert unchanged["status"] == "unchanged"


def test_retries_transient_network_failure_and_records_attempts(tmp_path):
    body = b"PAR1validPAR1"
    calls = 0
    pauses: list[float] = []

    def urlopen(_request, timeout):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise URLError("temporary network problem")
        return FakeResponse(body)

    store = FakeMetadataRepository()
    result = download_yellow_taxi(
        "2024-01",
        data_dir=tmp_path / "data",
        metadata=store,
        urlopen=urlopen,
        sleep=pauses.append,
    )

    assert result["attempts"] == 2
    assert calls == 2
    assert pauses == [1]


def test_failed_download_is_recorded_and_partial_file_removed(tmp_path):
    store = FakeMetadataRepository()

    def urlopen(_request, timeout):
        return FakeResponse(b"not parquet")

    with pytest.raises(RuntimeError, match="Parquet file magic"):
        download_yellow_taxi(
            "2024-01",
            data_dir=tmp_path / "data",
            metadata=store,
            urlopen=urlopen,
            sleep=lambda _: None,
        )

    run = next(iter(store.runs.values()))
    assert run.status == "failed"
    assert run.error_message
    assert run.completed_at_utc.tzinfo == UTC
    assert store.releases == []
    assert not list((tmp_path / "data" / ".incoming").glob("*.part"))


@pytest.mark.parametrize("period", ["2024-00", "2024-13", "2024-1", "junk"])
def test_rejects_invalid_source_period(tmp_path, period):
    with pytest.raises(ValueError, match="period"):
        download_yellow_taxi(
            period,
            data_dir=tmp_path / "data",
            metadata=FakeMetadataRepository(),
        )


@pytest.mark.parametrize("timeout", [0, -1, float("nan"), float("inf")])
def test_rejects_invalid_timeout_before_creating_a_run(tmp_path, timeout):
    store = FakeMetadataRepository()
    with pytest.raises(ValueError, match="finite positive"):
        download_yellow_taxi(
            "2024-01",
            data_dir=tmp_path / "data",
            metadata=store,
            timeout_seconds=timeout,
        )
    assert store.runs == {}
