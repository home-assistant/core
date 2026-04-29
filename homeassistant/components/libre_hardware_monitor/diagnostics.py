"""Diagnostics support for Libre Hardware Monitor."""

from __future__ import annotations

from dataclasses import asdict, replace
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .coordinator import LibreHardwareMonitorConfigEntry, LibreHardwareMonitorData

TO_REDACT = {CONF_USERNAME, CONF_PASSWORD}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: LibreHardwareMonitorConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    lhm_data: LibreHardwareMonitorData = config_entry.runtime_data.data

    return {
        "config_entry_data": {
            **async_redact_data(dict(config_entry.data), TO_REDACT),
        },
        "lhm_data": _as_dict(lhm_data),
    }


def _as_dict(data: LibreHardwareMonitorData) -> dict[str, Any]:
    return asdict(
        replace(
            data,
            main_device_ids_and_names=dict(data.main_device_ids_and_names),  # type: ignore[arg-type]
            sensor_data=dict(data.sensor_data),  # type: ignore[arg-type]
        )
    )
