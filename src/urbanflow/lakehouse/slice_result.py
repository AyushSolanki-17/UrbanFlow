"""Typed result for a published Yellow Taxi slice."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SliceResult:
    """Summary of a published Yellow Taxi slice with typed table references."""

    period: str
    source_sha256: str
    source_row_count: int
    landing_table: str
    validated_table: str
    rejected_table: str
    demand_table: str
    input_rows: int
    validated_rows: int
    rejected_rows: int
    demand_rows: int
    landing_snapshot_id: int | None
    validated_snapshot_id: int | None
    demand_snapshot_id: int | None
    demand_schema: list[str]
    manifest_path: str

    # Backwards-compatible aliases for the previous medallion naming.
    # Access via attribute still works so existing callers/tests that read
    # ``bronze_table`` / ``silver_table`` etc keep passing during migration.
    @property
    def bronze_table(self) -> str:  # pragma: no cover - compat shim
        return self.landing_table

    @property
    def silver_table(self) -> str:  # pragma: no cover - compat shim
        return self.validated_table

    @property
    def quarantine_table(self) -> str:  # pragma: no cover - compat shim
        return self.rejected_table

    @property
    def gold_table(self) -> str:  # pragma: no cover - compat shim
        return self.demand_table

    @property
    def accepted_rows(self) -> int:  # pragma: no cover - compat shim
        return self.validated_rows

    @property
    def quarantined_rows(self) -> int:  # pragma: no cover - compat shim
        return self.rejected_rows

    @property
    def gold_rows(self) -> int:  # pragma: no cover - compat shim
        return self.demand_rows

    @property
    def bronze_snapshot_id(self) -> int | None:  # pragma: no cover - compat shim
        return self.landing_snapshot_id

    @property
    def silver_snapshot_id(self) -> int | None:  # pragma: no cover - compat shim
        return self.validated_snapshot_id

    @property
    def gold_snapshot_id(self) -> int | None:  # pragma: no cover - compat shim
        return self.demand_snapshot_id

    @property
    def gold_schema(self) -> list[str]:  # pragma: no cover - compat shim
        return self.demand_schema
