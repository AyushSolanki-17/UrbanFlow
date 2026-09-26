"""Create and reuse the configured metadata repository adapter."""

from functools import cache

from urbanflow.database.interfaces import MetadataRepository
from urbanflow.database.postgres import PostgresMetadataAdapter


@cache
def get_metadata_repository(conninfo: str) -> MetadataRepository:
    """Return the shared metadata adapter for a connection configuration.

    The adapter manages short-lived database connections per operation. Caching
    the repository instance shares its schema initialization and configuration,
    not a database connection.
    """
    return PostgresMetadataAdapter(conninfo)
