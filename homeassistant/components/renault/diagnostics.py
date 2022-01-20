"""Diagnostics support for Renault."""
from __future__ import annotations

from types import MappingProxyType
from typing import Any

from homeassistant.components.diagnostics import REDACTED
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntry

from . import RenaultHub
from .const import CONF_KAMEREON_ACCOUNT_ID, DOMAIN

TO_REDACT = (
    CONF_KAMEREON_ACCOUNT_ID,
    CONF_PASSWORD,
    CONF_USERNAME,
    "radioCode",
    "registrationNumber",
    "vin",
)


@callback
def _async_redact_data(data: MappingProxyType | dict) -> dict[str, Any]:
    """Redact sensitive data in a dict."""
    redacted = {**data}

    for key, value in redacted.items():
        if key in TO_REDACT:
            redacted[key] = REDACTED
        elif isinstance(value, dict):
            redacted[key] = _async_redact_data(value)
        elif isinstance(value, list):
            redacted[key] = [_async_redact_data(item) for item in value]

    return redacted


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    renault_hub: RenaultHub = hass.data[DOMAIN][entry.entry_id]

    return {
        "entry": {
            "title": entry.title,
            "data": _async_redact_data(entry.data),
        },
        "vehicles": [
            _async_redact_data(vehicle.details.raw_data)
            for vehicle in renault_hub.vehicles.values()
        ],
    }


async def async_get_device_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry, device: DeviceEntry
) -> dict:
    """Return diagnostics for a device."""
    renault_hub: RenaultHub = hass.data[DOMAIN][entry.entry_id]
    vin = next(iter(device.identifiers))[1]

    return {
        "details": _async_redact_data(renault_hub.vehicles[vin].details.raw_data),
    }
