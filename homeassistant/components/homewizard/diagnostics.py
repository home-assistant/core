"""Diagnostics support for P1 Monitor."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_IP_ADDRESS
from homeassistant.core import HomeAssistant

from .coordinator import HomeWizardConfigEntry

TO_REDACT = {
    CONF_IP_ADDRESS,
    "gas_unique_id",
    "id",
    "serial",
    "token",
    "unique_id",
    "unique_meter_id",
    "wifi_ssid",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: HomeWizardConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    data = entry.runtime_data.data

    return async_redact_data(
        {
            "entry": async_redact_data(entry.data, TO_REDACT),
            "data": asdict(data),
        },
        TO_REDACT,
    )
