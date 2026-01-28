"""Helpers for the Energy integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .data import PowerConfig


def generate_power_sensor_unique_id(source_type: str, config: PowerConfig) -> str:
    """Generate a unique ID for a power transform sensor."""
    if "stat_rate_inverted" in config:
        sensor_id = config["stat_rate_inverted"].replace(".", "_")
        return f"energy_power_{source_type}_inverted_{sensor_id}"
    if "stat_rate_from" in config and "stat_rate_to" in config:
        from_id = config["stat_rate_from"].replace(".", "_")
        to_id = config["stat_rate_to"].replace(".", "_")
        return f"energy_power_{source_type}_combined_{from_id}_{to_id}"
    # This case is impossible: schema validation (vol.Inclusive) ensures
    # stat_rate_from and stat_rate_to are always present together
    raise RuntimeError("Invalid power config: missing required keys")


def generate_power_sensor_entity_id(source_type: str, config: PowerConfig) -> str:
    """Generate an entity ID for a power transform sensor."""
    if "stat_rate_inverted" in config:
        # Use source sensor name with _inverted suffix
        source = config["stat_rate_inverted"]
        if source.startswith("sensor."):
            return f"{source}_inverted"
        return f"sensor.{source.replace('.', '_')}_inverted"
    if "stat_rate_from" in config and "stat_rate_to" in config:
        # Use both sensors in entity ID to ensure uniqueness when multiple
        # combined configs exist. The entity represents net power (from - to),
        # e.g., discharge - charge for battery.
        from_sensor = config["stat_rate_from"].removeprefix("sensor.")
        to_sensor = config["stat_rate_to"].removeprefix("sensor.")
        return f"sensor.energy_{source_type}_{from_sensor}_{to_sensor}_net_power"
    # This case is impossible: schema validation (vol.Inclusive) ensures
    # stat_rate_from and stat_rate_to are always present together
    raise RuntimeError("Invalid power config: missing required keys")
