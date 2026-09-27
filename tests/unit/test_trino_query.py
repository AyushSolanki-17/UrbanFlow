"""Tests for the read-only hourly demand demo query."""

from datetime import datetime

import pytest

from urbanflow.lakehouse.query import query_hourly_zone_demand


class FakeCursor:
    def __init__(self):
        self.query = None
        self.parameters = None
        self.closed = False
        self.description = []
        self.rows = []

    def execute(self, query, parameters=()):
        self.query = query
        self.parameters = parameters
        if query.startswith("DESCRIBE"):
            self.description = [("Column",), ("Type",)]
            self.rows = [
                (name, "varchar")
                for name in ("city", "zone", "hour", "trip_count", "source_period")
            ]
        else:
            self.description = [("city",), ("zone",), ("hour",), ("trip_count",)]
            self.rows = [("NYC", 1, datetime(2024, 1, 1), 42)]

    def fetchall(self):
        return self.rows

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(self):
        self.fake_cursor = FakeCursor()
        self.closed = False

    def cursor(self):
        return self.fake_cursor

    def close(self):
        self.closed = True


def test_query_uses_bound_filters_and_closes_trino_resources(monkeypatch):
    import trino

    connection = FakeConnection()
    settings = {}

    def connect(**kwargs):
        settings.update(kwargs)
        return connection

    monkeypatch.setattr(trino.dbapi, "connect", connect)

    rows = query_hourly_zone_demand("2024-01", limit=7)

    assert rows[0]["zone"] == 1
    assert rows[0]["trip_count"] == 42
    assert connection.fake_cursor.parameters == ("2024-01", 7)
    assert "FROM iceberg.gold.zone_hour_demand" in connection.fake_cursor.query
    assert settings["catalog"] == "iceberg"
    assert settings["schema"] == "gold"
    assert connection.fake_cursor.closed
    assert connection.closed


@pytest.mark.parametrize("period,limit", [("2024-13", 10), ("2024-01", 0), ("2024-01", 101)])
def test_query_rejects_invalid_period_or_unbounded_limit(period, limit):
    with pytest.raises(ValueError):
        query_hourly_zone_demand(period, limit=limit)
