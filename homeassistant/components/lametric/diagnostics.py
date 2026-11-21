"""Diagnostics support for LaMetric."""

import json
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .coordinator import LaMetricConfigEntry

TO_REDACT = {
    "device_id",
    "name",
    "serial_number",
    "ssid",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: LaMetricConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    runtime_data = entry.runtime_data
    # Round-trip via JSON to trigger serialization
    data = json.loads(runtime_data.device.data.to_json())
    # Apps are only reported by devices with firmware 2.1.0 and newer.
    if (apps := runtime_data.apps.data) is not None:
        # The widget settings hold user-defined titles and configuration.
        data["apps"] = async_redact_data(
            {package: json.loads(app.to_json()) for package, app in apps.items()},
            {"settings"},
        )
    return async_redact_data(data, TO_REDACT)
