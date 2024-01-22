"""Diagnostics support for Sensibo."""
from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics.util import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import SensiboDataUpdateCoordinator

TO_REDACT = {
    "location",
    "ssid",
    "id",
    "macAddress",
    "parentDeviceUid",
    "qrId",
    "serial",
    "uid",
    "email",
    "firstName",
    "lastName",
    "username",
    "podUid",
    "deviceUid",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for Sensibo config entry."""
    coordinator: SensiboDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    diag_data = {}
    diag_data["raw"] = async_redact_data(coordinator.data.raw, TO_REDACT)
    for device, device_data in coordinator.data.parsed.items():
        diag_data[device] = async_redact_data(device_data.__dict__, TO_REDACT)
    return diag_data
