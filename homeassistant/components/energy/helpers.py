"""Helpers for the Energy integration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def generate_power_sensor_unique_id(source_type: str, config: Mapping[str, Any]) -> str:
    """Generate a unique ID for a power transform sensor."""
    if "stat_rate_inverted" in config:
        sensor_id = config["stat_rate_inverted"].replace(".", "_")
        return f"energy_power_{source_type}_inv_{sensor_id}"
    if "stat_rate_from" in config and "stat_rate_to" in config:
        from_id = config["stat_rate_from"].replace(".", "_")
        to_id = config["stat_rate_to"].replace(".", "_")
        return f"energy_power_{source_type}_combined_{from_id}_{to_id}"
    return ""


def generate_power_sensor_entity_id(source_type: str, config: Mapping[str, Any]) -> str:
    """Generate an entity ID for a power transform sensor."""
    if "stat_rate_inverted" in config:
        # Use source sensor name with _inverted suffix
        source = config["stat_rate_inverted"]
        if source.startswith("sensor."):
            return f"{source}_inverted"
        return f"sensor.{source.replace('.', '_')}_inverted"
    if "stat_rate_from" in config and "stat_rate_to" in config:
        # Include sensor IDs to avoid collisions when multiple combined configs exist
        from_sensor = config["stat_rate_from"].removeprefix("sensor.")
        return f"sensor.energy_{source_type}_{from_sensor}_power"
    return ""
