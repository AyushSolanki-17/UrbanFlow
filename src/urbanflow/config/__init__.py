"""Load explicit environment settings without creating runtime state."""

import math
import tomllib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class LocalSettings:
    """Planning budgets in decimal GB; these do not enforce runtime admission."""

    data_dir: Path
    working_data_target_gb: float
    working_data_peak_gb: float
    stack_memory_budget_gb: float


def load_settings(path: Path) -> LocalSettings:
    """Read a strict TOML profile; relative data paths resolve beside the profile."""
    with path.open("rb") as source:
        document = tomllib.load(source)
    if set(document) != {"local"} or not isinstance(document["local"], dict):
        raise ValueError("configuration must contain only a [local] table")
    values = document["local"]
    expected = {
        "data_dir",
        "working_data_target_gb",
        "working_data_peak_gb",
        "stack_memory_budget_gb",
    }
    if set(values) != expected:
        missing = sorted(expected - set(values))
        unknown = sorted(set(values) - expected)
        raise ValueError(f"invalid local settings: missing={missing}, unknown={unknown}")
    data_dir = values["data_dir"]
    if not isinstance(data_dir, str) or not data_dir.strip():
        raise ValueError("data_dir must be a non-empty path string")
    budgets = {}
    for key in sorted(expected - {"data_dir"}):
        value = values[key]
        if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
            raise ValueError(f"{key} must be a finite positive number")
        budgets[key] = float(value)
    if budgets["working_data_target_gb"] > budgets["working_data_peak_gb"]:
        raise ValueError("working_data_target_gb must not exceed working_data_peak_gb")
    resolved_dir = Path(data_dir).expanduser()
    if not resolved_dir.is_absolute():
        resolved_dir = path.resolve().parent / resolved_dir
    return LocalSettings(data_dir=resolved_dir.resolve(), **budgets)
