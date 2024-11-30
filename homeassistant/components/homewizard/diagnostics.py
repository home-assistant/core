"""Diagnostics support for P1 Monitor."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_IP_ADDRESS
from homeassistant.core import HomeAssistant

from . import HomeWizardConfigEntry

TO_REDACT = {
    CONF_IP_ADDRESS,
    "serial",
    "wifi_ssid",
    "unique_meter_id",
    "unique_id",
    "gas_unique_id",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: HomeWizardConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    data = entry.runtime_data.data

    state: dict[str, Any] | None = None
    if data.state:
        state = asdict(data.state)

    system: dict[str, Any] | None = None
    if data.system:
        system = asdict(data.system)

    return async_redact_data(
        {
            "entry": async_redact_data(entry.data, TO_REDACT),
            "data": {
                "device": asdict(data.device),
                "data": asdict(data.data),
                "state": state,
                "system": system,
            },
        },
        TO_REDACT,
    )
