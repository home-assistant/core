"""Diagnostics support for Leneda."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.redact import async_redact_data

from .const import CONF_ENERGY_ID, CONF_METERING_POINTS

TO_REDACT = [CONF_ENERGY_ID, CONF_API_TOKEN, CONF_METERING_POINTS]


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> Mapping[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = config_entry.runtime_data
    entry_data = coordinator.data

    # Anonymize metering point keys
    def anonymize_key(key: str) -> str:
        if len(key) <= 6:
            return key
        return key[:6] + ("#" * (len(key) - 6))

    # Anonymize metering points in data
    anonymized_data = (
        {anonymize_key(mp): value for mp, value in entry_data.items()}
        if isinstance(entry_data, dict)
        else entry_data
    )

    # Anonymize metering points in selected_sensors
    selected_sensors = getattr(coordinator, "selected_sensors", {})
    anonymized_selected_sensors = {
        anonymize_key(mp): sensors for mp, sensors in selected_sensors.items()
    }

    return {
        "user_config": {
            "selected_sensors": anonymized_selected_sensors,
        },
        "data": async_redact_data(dict(config_entry.data), TO_REDACT),
        "entry_data": anonymized_data,
    }
