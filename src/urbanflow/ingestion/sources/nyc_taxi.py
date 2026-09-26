"""Download monthly NYC TLC Yellow Taxi trip files."""

import hashlib
import math
import os
import shutil
import time
import urllib.error
import urllib.request
import uuid
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol, TypedDict

from urbanflow.database import MetadataRepository
from urbanflow.database.models import IngestionRun

SOURCE_ID = "nyc_tlc.yellow_taxi"
SOURCE_URL_TEMPLATE = (
    "https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_{period}.parquet"
)
_RETRYABLE_HTTP_CODES = {408, 429, 500, 502, 503, 504}
_CHUNK_SIZE = 1024 * 1024


class DownloadResult(TypedDict):
    """Serializable summary returned after a source-download attempt."""

    run_id: str
    source_id: str
    source_period: str
    source_url: str
    status: str
    started_at_utc: str
    completed_at_utc: str | None
    file_path: str | None
    byte_count: int | None
    sha256: str | None
    etag: str | None
    source_last_modified: str | None
    attempts: int


class DownloadResponse(Protocol):
    """Small response surface required from urllib or a test response."""

    headers: Mapping[str, str]

    def read(self, size: int = -1) -> bytes:
        """Read at most ``size`` bytes from the response body."""

    def __enter__(self) -> "DownloadResponse":
        """Enter the response context."""

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        """Close the response context."""


def validate_period(period: str) -> str:
    """Validate and return a TLC monthly source period.

    Args:
        period: Year and month in ``YYYY-MM`` format.

    Returns:
        The validated period string.

    Raises:
        ValueError: If the value is not a valid year and month.
    """
    try:
        parsed = datetime.strptime(period, "%Y-%m")
    except ValueError as error:
        raise ValueError("period must use YYYY-MM and contain a valid month") from error
    if parsed.strftime("%Y-%m") != period:
        raise ValueError("period must use YYYY-MM")
    return period


def download_yellow_taxi(
    period: str,
    *,
    data_dir: Path,
    metadata: MetadataRepository,
    refresh: bool = False,
    timeout_seconds: float = 60,
    max_retries: int = 3,
    urlopen: Callable[[urllib.request.Request, float], DownloadResponse] = urllib.request.urlopen,
    sleep: Callable[[float], None] = time.sleep,
) -> DownloadResult:
    """Download a monthly Yellow Taxi Parquet release and record its provenance.

    The URL is derived from the requested period, so the workflow needs no browser,
    manual file selection, or third-party SDK. Releases are stored by SHA-256 to
    preserve corrections as separate immutable files. Failed runs retain metadata.

    Args:
        period: TLC source month in ``YYYY-MM`` form.
        data_dir: Configured root directory for downloaded source data.
        metadata: Adapter used to store run and release metadata.
        refresh: Re-download even when the latest recorded release is present locally.
        timeout_seconds: Timeout applied to each HTTP request.
        max_retries: Maximum retries after the initial request.
        urlopen: HTTP opener, exposed for deterministic tests.
        sleep: Backoff function, exposed for deterministic tests.

    Returns:
        A JSON-serializable summary of the completed download or unchanged release.

    Raises:
        ValueError: If period or retry/timeout settings are invalid.
        RuntimeError: If the source request or downloaded file validation fails.
    """
    validate_period(period)
    if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be a finite positive number")
    if max_retries < 0:
        raise ValueError("max_retries must be zero or greater")

    source_url = SOURCE_URL_TEMPLATE.format(period=period)
    run_id = uuid.uuid4()
    started_at = _utc_now()
    metadata.begin_run(
        IngestionRun(
            run_id=run_id,
            source_id=SOURCE_ID,
            source_period=period,
            source_url=source_url,
            status="downloading",
            started_at_utc=started_at,
        )
    )

    try:
        previous = metadata.latest_release(SOURCE_ID, period)
        if previous and not refresh:
            previous_path = previous.file_path
            if previous_path.is_file() and _sha256(previous_path) == previous.sha256:
                completed = _utc_now()
                unchanged = IngestionRun(
                    run_id=run_id,
                    source_id=SOURCE_ID,
                    source_period=period,
                    source_url=source_url,
                    status="unchanged",
                    started_at_utc=started_at,
                    completed_at_utc=completed,
                    file_path=previous_path,
                    byte_count=previous.byte_count,
                    sha256=previous.sha256,
                    etag=previous.etag,
                    source_last_modified=previous.source_last_modified,
                    attempts=0,
                )
                metadata.complete_run(unchanged, unchanged=True)
                return _result(unchanged, unchanged=True)
    except Exception as error:
        metadata.fail_run(
            run_id,
            completed_at_utc=_utc_now(),
            attempts=0,
            error=f"{type(error).__name__}: {error}",
        )
        raise

    incoming_dir = data_dir / ".incoming"
    temp_path = incoming_dir / f"{run_id}.part"
    attempts = 0
    try:
        incoming_dir.mkdir(parents=True, exist_ok=True)
        for attempt in range(max_retries + 1):
            attempts = attempt + 1
            metadata.update_attempt(run_id, attempts)
            try:
                headers, byte_count, digest = _fetch(
                    source_url,
                    temp_path,
                    timeout_seconds=timeout_seconds,
                    urlopen=urlopen,
                    data_dir=data_dir,
                )
                break
            except urllib.error.HTTPError as error:
                if error.code not in _RETRYABLE_HTTP_CODES or attempt == max_retries:
                    raise RuntimeError(f"TLC download failed with HTTP {error.code}") from error
            except (urllib.error.URLError, TimeoutError, OSError) as error:
                if attempt == max_retries:
                    raise RuntimeError(
                        f"TLC download failed after {attempts} attempts: {error}"
                    ) from error
            temp_path.unlink(missing_ok=True)
            sleep(min(30, 2**attempt))

        release_dir = (
            data_dir
            / "bronze"
            / "raw"
            / "source=nyc_tlc"
            / "service=yellow"
            / f"period={period}"
            / f"release=sha256-{digest}"
        )
        release_dir.mkdir(parents=True, exist_ok=True)
        filename = f"yellow_tripdata_{period}.parquet"
        release_path = release_dir / filename
        try:
            os.link(temp_path, release_path)
        except FileExistsError as error:
            if release_path.stat().st_size != byte_count or _sha256(release_path) != digest:
                raise RuntimeError(
                    f"existing release path has content that does not match SHA-256: {release_path}"
                ) from error
        temp_path.unlink(missing_ok=True)

        completed = _utc_now()
        run = IngestionRun(
            run_id=run_id,
            source_id=SOURCE_ID,
            source_period=period,
            source_url=source_url,
            status="succeeded",
            started_at_utc=started_at,
            completed_at_utc=completed,
            file_path=release_path,
            byte_count=byte_count,
            sha256=digest,
            etag=headers.get("ETag"),
            source_last_modified=headers.get("Last-Modified"),
            attempts=attempts,
        )
        metadata.complete_run(run)
        return _result(run, unchanged=False)
    except Exception as error:
        temp_path.unlink(missing_ok=True)
        metadata.fail_run(
            run_id,
            completed_at_utc=_utc_now(),
            attempts=attempts,
            error=f"{type(error).__name__}: {error}",
        )
        raise


def _fetch(
    url: str,
    destination: Path,
    *,
    timeout_seconds: float,
    urlopen: Callable[[urllib.request.Request, float], DownloadResponse],
    data_dir: Path,
) -> tuple[dict[str, str], int, str]:
    """Stream one HTTP response to disk while verifying length and Parquet framing."""
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "UrbanFlow/0.1 (NYC TLC historical data ingestion)"},
    )
    digest = hashlib.sha256()
    byte_count = 0
    with urlopen(request, timeout=timeout_seconds) as response, destination.open("wb") as output:
        headers = dict(response.headers.items())
        content_length = headers.get("Content-Length")
        if content_length is not None:
            try:
                expected_bytes = int(content_length)
            except ValueError as error:
                raise RuntimeError("source returned an invalid Content-Length header") from error
            if expected_bytes > shutil.disk_usage(data_dir).free:
                raise RuntimeError(
                    f"insufficient free space for source object: {expected_bytes} bytes required"
                )
        while chunk := response.read(_CHUNK_SIZE):
            output.write(chunk)
            digest.update(chunk)
            byte_count += len(chunk)
        output.flush()
    if content_length is not None and byte_count != expected_bytes:
        raise RuntimeError(
            f"incomplete source object: expected {expected_bytes} bytes, received {byte_count}"
        )
    if byte_count < 8:
        raise RuntimeError("download is too small to be a Parquet file")
    with destination.open("rb") as source:
        header = source.read(4)
        source.seek(-4, 2)
        footer = source.read(4)
    if header != b"PAR1" or footer != b"PAR1":
        raise RuntimeError("download does not have Parquet file magic bytes")
    return headers, byte_count, digest.hexdigest()


def _sha256(path: Path) -> str:
    """Calculate a file checksum in bounded memory."""
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(_CHUNK_SIZE):
            digest.update(chunk)
    return digest.hexdigest()


def _utc_now() -> datetime:
    """Return the current timezone-aware UTC instant."""
    return datetime.now(UTC)


def _result(run: IngestionRun, *, unchanged: bool) -> DownloadResult:
    """Build the stable JSON summary returned by the CLI."""
    return {
        "run_id": str(run.run_id),
        "source_id": run.source_id,
        "source_period": run.source_period,
        "source_url": run.source_url,
        "status": "unchanged" if unchanged else "succeeded",
        "started_at_utc": run.started_at_utc.isoformat().replace("+00:00", "Z"),
        "completed_at_utc": (
            run.completed_at_utc.isoformat().replace("+00:00", "Z")
            if run.completed_at_utc is not None
            else None
        ),
        "file_path": str(run.file_path) if run.file_path is not None else None,
        "byte_count": run.byte_count,
        "sha256": run.sha256,
        "etag": run.etag,
        "source_last_modified": run.source_last_modified,
        "attempts": run.attempts,
    }
