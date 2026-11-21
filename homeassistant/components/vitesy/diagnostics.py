"""Diagnostics support for the Vitesy integration."""

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant

from .coordinator import VitesyConfigEntry

TO_REDACT = {CONF_EMAIL, CONF_PASSWORD}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: VitesyConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    return {
        "entry_data": async_redact_data(entry.data, TO_REDACT),
        "devices": async_redact_data(
            {
                device_id: asdict(device)
                for device_id, device in coordinator.data.items()
            },
            TO_REDACT,
        ),
        "mode_status": {
            device_id: asdict(status)
            for device_id, status in coordinator.mode_status.items()
        },
    }
