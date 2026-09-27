"""Typed rejection reasons for Yellow Taxi validation."""

from enum import StrEnum


class RejectionReason(StrEnum):
    """Why a trip row was routed to the rejected dataset.

    Values are stable strings stored in the ``rejection_reason`` column
    so downstream consumers can filter without stringly-typed checks.
    """

    MISSING_TIMESTAMPS = "missing_pickup_or_dropoff"
    DROPOFF_BEFORE_PICKUP = "dropoff_before_pickup"
    INVALID_PICKUP_ZONE = "invalid_pickup_zone"
    INVALID_DROPOFF_ZONE = "invalid_dropoff_zone"
    NEGATIVE_DISTANCE = "negative_distance"
    NEGATIVE_FARE = "negative_fare"
    INVALID_PASSENGER_COUNT = "invalid_passenger_count"
