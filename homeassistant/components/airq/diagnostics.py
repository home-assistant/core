"""Diagnostics support for air-Q."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_PASSWORD
from homeassistant.core import HomeAssistant

from . import AirQConfigEntry

REDACT_CONFIG = {CONF_PASSWORD}
REDACT_DATA = {"device_id"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: AirQConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data

    return {
        "config_entry": async_redact_data(entry.as_dict(), REDACT_CONFIG),
        "device_info": async_redact_data(dict(coordinator.device_info), REDACT_DATA),
        "coordinator_data": coordinator.data,
        "options": {
            "clip_negative": coordinator.clip_negative,
            "return_average": coordinator.return_average,
        },
    }
