"""Typed Iceberg table identifiers for the lakehouse."""

from dataclasses import dataclass
from typing import Literal

LakehouseNamespace = Literal["bronze", "silver", "gold"]


@dataclass(frozen=True, slots=True)
class TableIdentifier:
    """Fully-qualified Iceberg table name with a typed namespace."""

    namespace: LakehouseNamespace
    name: str

    def __str__(self) -> str:
        return f"{self.namespace}.{self.name}"


# Keep physical identifiers aligned with the published source contract.
LANDING_RAW_YELLOW_TRIPS = TableIdentifier("bronze", "raw_yellow_trips")
CURATED_VALIDATED_YELLOW_TRIPS = TableIdentifier("silver", "clean_trips")
CURATED_REJECTED_YELLOW_TRIPS = TableIdentifier("silver", "quarantine_yellow_trips")
SERVING_HOURLY_ZONE_DEMAND = TableIdentifier("gold", "zone_hour_demand")
