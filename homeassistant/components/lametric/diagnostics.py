"""Diagnostics support for LaMetric."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from homeassistant.components.diagnostics import async_redact_data

from .const import DOMAIN

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

    from .coordinator import LaMetricDataUpdateCoordinator

TO_REDACT = {
    "device_id",
    "name",
    "serial_number",
    "ssid",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: LaMetricDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    # Round-trip via JSON to trigger serialization
    data = json.loads(coordinator.data.json())
    return async_redact_data(data, TO_REDACT)
