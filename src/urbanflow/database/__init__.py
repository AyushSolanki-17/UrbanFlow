"""Reusable metadata persistence adapters."""

from urbanflow.database.factory import get_metadata_repository
from urbanflow.database.interfaces import MetadataRepository

__all__ = ["MetadataRepository", "get_metadata_repository"]
