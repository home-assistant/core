"""Diagnostics support for Switcher."""
from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DATA_DEVICE, DOMAIN

TO_REDACT = {"device_id", "device_key", "ip_address", "mac_address"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    devices = hass.data[DOMAIN][DATA_DEVICE]

    return async_redact_data(
        {
            "entry": entry.as_dict(),
            "devices": [asdict(devices[d].data) for d in devices],
        },
        TO_REDACT,
    )
