"""Read-only Trino query for the bounded Yellow Taxi demo."""

from typing import Any

from urbanflow.ingestion.sources.nyc_taxi import validate_period

_DESCRIBE_QUERY = "DESCRIBE iceberg.gold.zone_hour_demand"
_DEMAND_QUERY = """
SELECT city, zone, hour, trip_count, avg_distance, avg_fare, sum_fare
FROM iceberg.gold.zone_hour_demand
ORDER BY trip_count DESC, zone, hour
LIMIT ?
"""
_PERIOD_DEMAND_QUERY = _DEMAND_QUERY.replace("ORDER BY", "WHERE source_period = ?\nORDER BY")


def query_hourly_zone_demand(
    period: str | None = None,
    *,
    host: str = "localhost",
    port: int = 8080,
    user: str = "urbanflow",
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Return the highest-volume hourly zones for one published source month.

    Args:
        period: Optional published source month in ``YYYY-MM`` format.
        host: Trino coordinator host.
        port: Trino coordinator HTTP port.
        user: Trino user label for the local unauthenticated coordinator.
        limit: Maximum result rows, capped at 100 for the demo.

    Returns:
        Rows ordered by trip count descending.

    Raises:
        ValueError: If a query argument is invalid.
        RuntimeError: If Trino cannot execute the query.
    """
    if period is not None:
        validate_period(period)
    if not host.strip():
        raise ValueError("Trino host must not be empty")
    if not 1 <= port <= 65535:
        raise ValueError("Trino port must be between 1 and 65535")
    if not 1 <= limit <= 100:
        raise ValueError("query limit must be between 1 and 100")

    import trino

    connection = None
    cursor = None
    try:
        connection = trino.dbapi.connect(
            host=host,
            port=port,
            user=user,
            catalog="iceberg",
            schema="gold",
        )
        cursor = connection.cursor()
        cursor.execute(_DESCRIBE_QUERY)
        available_columns = {row[0] for row in cursor.fetchall()}
        if period is not None and "source_period" not in available_columns:
            raise RuntimeError(
                "this Gold table predates period provenance; "
                "republish it before filtering by period"
            )
        if period is None:
            cursor.execute(_DEMAND_QUERY, (limit,))
        else:
            cursor.execute(_PERIOD_DEMAND_QUERY, (period, limit))
        columns = [column[0] for column in cursor.description]
        return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]
    except Exception as error:
        raise RuntimeError(f"Trino demand query failed: {error}") from error
    finally:
        if cursor is not None:
            cursor.close()
        if connection is not None:
            connection.close()
