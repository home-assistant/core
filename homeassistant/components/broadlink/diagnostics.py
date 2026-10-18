"""Diagnostics support for Broadlink."""

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_MAC
from homeassistant.core import HomeAssistant

from .const import BROADLINK_DATA

TO_REDACT = {CONF_HOST, CONF_MAC}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    device = hass.data[BROADLINK_DATA].devices[entry.entry_id]
    assert device.update_manager is not None
    coordinator = device.update_manager.coordinator
    return {
        "entry": async_redact_data(entry.data, TO_REDACT),
        "device": {
            "type": device.api.type,
            "devtype": device.api.devtype,
            "model": device.api.model,
            "manufacturer": device.api.manufacturer,
            "fw_version": device.fw_version,
            "available": device.available,
        },
        "data": coordinator.data,
    }
