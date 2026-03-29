"""Diagnostics support for OPNsense."""

from __future__ import annotations

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_URL, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntry

from .const import COORDINATOR, DEVICE_TRACKER_COORDINATOR

TO_REDACT = {
    CONF_PASSWORD,
    CONF_URL,
    CONF_USERNAME,
    "device_unique_id",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, object]:
    """Return diagnostics for a config entry."""
    runtime_data = entry.runtime_data
    return async_redact_data(
        {
            "entry": entry.as_dict(),
            "coordinator": getattr(runtime_data, COORDINATOR).data
            if runtime_data
            else None,
            "device_tracker_coordinator": (
                getattr(runtime_data, DEVICE_TRACKER_COORDINATOR).data
                if runtime_data
                and getattr(runtime_data, DEVICE_TRACKER_COORDINATOR, None)
                else None
            ),
        },
        TO_REDACT,
    )


async def async_get_device_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry, device: DeviceEntry
) -> dict[str, object]:
    """Return diagnostics for a device."""
    diagnostics = await async_get_config_entry_diagnostics(hass, entry)
    diagnostics["device"] = async_redact_data(device.dict_repr, TO_REDACT)
    return diagnostics
