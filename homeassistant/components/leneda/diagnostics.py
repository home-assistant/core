"""Diagnostics support for Leneda."""

from __future__ import annotations

from collections.abc import Mapping
import datetime
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> Mapping[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = config_entry.runtime_data
    data = coordinator.data

    # Anonymize metering point keys
    def anonymize_key(key: str) -> str:
        if len(key) <= 6:
            return key
        return key[:6] + ("#" * (len(key) - 6))

    # Anonymize metering points in data
    anonymized_data = (
        {anonymize_key(mp): value for mp, value in data.items()}
        if isinstance(data, dict)
        else data
    )

    # Anonymize metering points in selected_sensors
    selected_sensors = getattr(coordinator, "selected_sensors", {})
    anonymized_selected_sensors = {
        anonymize_key(mp): sensors for mp, sensors in selected_sensors.items()
    }

    # Anonymize metering points list
    metering_points = getattr(coordinator, "metering_points", [])
    anonymized_metering_points = [anonymize_key(mp) for mp in metering_points]

    # Coordinator state
    last_update_success = getattr(coordinator, "last_update_success", None)
    last_update_time = getattr(coordinator, "last_update_time", None)
    last_exception = getattr(coordinator, "last_exception", None)
    update_interval = getattr(coordinator, "update_interval", None)
    if isinstance(update_interval, datetime.timedelta):
        update_interval = str(update_interval)
    if isinstance(last_update_time, datetime.datetime):
        last_update_time = last_update_time.isoformat()
    if last_exception:
        last_exception = str(last_exception)

    # Config entry metadata
    config_entry_info = {
        "entry_id": config_entry.entry_id,
        "domain": config_entry.domain,
        "source": getattr(config_entry, "source", None),
        "version": getattr(config_entry, "version", None),
        "created_at": getattr(config_entry, "created_at", None),
        "modified_at": getattr(config_entry, "modified_at", None),
    }

    return {
        "config_entry": config_entry_info,
        "coordinator": {
            "update_interval": update_interval,
            "last_update_success": last_update_success,
            "last_update_time": last_update_time,
            "last_exception": last_exception,
        },
        "user_config": {
            "metering_points": anonymized_metering_points,
            "selected_sensors": anonymized_selected_sensors,
        },
        "data": anonymized_data,
    }
