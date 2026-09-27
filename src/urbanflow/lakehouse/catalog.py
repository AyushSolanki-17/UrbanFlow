"""Shared Iceberg catalog helpers for the lakehouse.

This module provides the minimal catalog/warehouse configuration shared
between the PyIceberg writer and Trino. Both coordinate through the
same JDBC-backed catalog and warehouse directory.
"""

from pathlib import Path
from urllib.parse import urlsplit

from pyiceberg.catalog import load_catalog as _load_catalog


def default_warehouse_path(project_root: Path | None = None) -> Path:
    """Return the local file warehouse path.

    The warehouse lives under ignored ``.local`` storage so it does not
    become a repository fixture. Trino mounts the same absolute host
    path inside its container (both at the host absolute path and at
    the ``/tmp``-prefixed path that Trino's local filesystem prefixes).
    """
    if project_root is None:
        # ``src/urbanflow/lakehouse/catalog.py`` -> repo root
        project_root = Path(__file__).resolve().parents[3]
    return (project_root / ".local" / "spike-iceberg" / "warehouse").resolve()


def load_catalog(
    warehouse: Path | str | None = None,
    uri: str | None = None,
    catalog_name: str = "spike_pg",
):
    """Load the ``sql`` Iceberg catalog backed by PostgreSQL.

    Args:
        warehouse: Local file warehouse directory. Defaults to the
            repository's ``.local/spike-iceberg/warehouse``.
        uri: SQLAlchemy URI for the catalog backend. Defaults to the
            ``URBANFLOW_METADATA_DATABASE_URL``-style PostgreSQL URI
            with ``postgresql+psycopg2://``.
        catalog_name: Iceberg catalog name stored in the
            ``iceberg_tables.catalog_name`` column and mirrored in
            Trino's ``iceberg.jdbc-catalog.catalog-name``.

    The catalog uses the same PostgreSQL database as the metadata
    adapter but is isolated by ``catalog_name``. Trino shares the same
    database via its JDBC catalog.
    """
    if warehouse is None:
        warehouse_path = default_warehouse_path()
    else:
        warehouse_path = Path(warehouse).resolve()
    warehouse_path.mkdir(parents=True, exist_ok=True)

    if uri is None:
        # Import locally to avoid circular import when config changes.
        import os

        base_url = os.environ.get(
            "URBANFLOW_METADATA_DATABASE_URL",
            "postgresql://urbanflow@localhost:5432/urbanflow",
        )
        # Convert postgres:// to sqlalchemy form expected by PyIceberg.
        parsed = urlsplit(base_url)
        scheme = parsed.scheme
        if scheme in ("postgres", "postgresql"):
            # PyIceberg's SQL catalog expects postgresql+psycopg2://
            uri = base_url.replace(f"{scheme}://", "postgresql+psycopg2://", 1)
        else:
            uri = base_url
        # Inject spike password from .env if default localhost URL is used
        # and password is not present. Prefer explicit env.
        if "@localhost" in uri and "kaG9i" not in uri:
            try:
                env_path = Path(__file__).resolve().parents[3] / ".env"
                if env_path.exists():
                    for line in env_path.read_text().splitlines():
                        if line.startswith("POSTGRES_PASSWORD="):
                            pwd = line.split("=", 1)[1].strip()
                            if pwd and "urbanflow@localhost" in uri:
                                uri = uri.replace(
                                    "urbanflow@localhost", f"urbanflow:{pwd}@localhost"
                                )
                            break
            except OSError:
                pass

    return _load_catalog(
        catalog_name,
        **{
            "type": "sql",
            "uri": uri,
            "warehouse": warehouse_path.as_uri(),
        },
    )


def load_spike_catalog(*args, **kwargs):
    """Compatibility alias for :func:`load_catalog`."""
    return load_catalog(*args, **kwargs)


def load_s3_catalog(
    warehouse: str = "s3://warehouse",
    uri: str | None = None,
    catalog_name: str = "spike_pg",
    s3_endpoint: str = "http://localhost:9090",
    s3_access_key: str = "test",
    s3_secret_key: str = "test",
    s3_region: str = "us-east-1",
):
    """Load the catalog with an S3 warehouse (MinIO / S3Mock).

    Reuses the same PostgreSQL JDBC catalog as the file variant so
    tables can coexist. S3 FileIO properties are supplied so PyIceberg
    writes Parquet and metadata to ``s3://warehouse`` via the S3Mock
    endpoint.

    Args:
        warehouse: S3 warehouse location (e.g. ``s3://warehouse``).
        uri: SQLAlchemy URI for the catalog backend; defaults to the
            PostgreSQL spike catalog.
        catalog_name: Must match Trino's
            ``iceberg.jdbc-catalog.catalog-name``.
        s3_endpoint: S3Mock/MinIO endpoint reachable from the host.
        s3_access_key: S3 access key (S3Mock accepts any).
        s3_secret_key: S3 secret key.
        s3_region: S3 region for signing.
    """
    if uri is None:
        import os

        base_url = os.environ.get(
            "URBANFLOW_METADATA_DATABASE_URL",
            "postgresql://urbanflow@localhost:5432/urbanflow",
        )
        parsed = urlsplit(base_url)
        scheme = parsed.scheme
        if scheme in ("postgres", "postgresql"):
            uri = base_url.replace(f"{scheme}://", "postgresql+psycopg2://", 1)
        else:
            uri = base_url
        if "@localhost" in uri and "kaG9i" not in uri:
            try:
                env_path = Path(__file__).resolve().parents[3] / ".env"
                if env_path.exists():
                    for line in env_path.read_text().splitlines():
                        if line.startswith("POSTGRES_PASSWORD="):
                            pwd = line.split("=", 1)[1].strip()
                            if pwd and "urbanflow@localhost" in uri:
                                uri = uri.replace(
                                    "urbanflow@localhost", f"urbanflow:{pwd}@localhost"
                                )
                            break
            except OSError:
                pass

    return _load_catalog(
        catalog_name,
        **{
            "type": "sql",
            "uri": uri,
            "warehouse": warehouse,
            "s3.endpoint": s3_endpoint,
            "s3.access-key-id": s3_access_key,
            "s3.secret-access-key": s3_secret_key,
            "s3.region": s3_region,
            "s3.path-style-access": "true",
        },
    )


def load_spike_s3_catalog(*args, **kwargs):
    """Compatibility alias for :func:`load_s3_catalog`."""
    return load_s3_catalog(*args, **kwargs)
