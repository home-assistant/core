"""Diagnostics support for Shelly."""
from __future__ import annotations

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.components.shelly import BlockDeviceWrapper, RpcDeviceWrapper
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .const import BLOCK, DATA_CONFIG_ENTRY, DOMAIN, RPC

TO_REDACT = {CONF_USERNAME, CONF_PASSWORD}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict:
    """Return diagnostics for a config entry."""
    data: dict = hass.data[DOMAIN][DATA_CONFIG_ENTRY][entry.entry_id]

    if BLOCK in data:
        wrapper = data.get(BLOCK)
    else:
        wrapper = data.get(RPC)

    assert isinstance(wrapper, (BlockDeviceWrapper, RpcDeviceWrapper))

    return {
        "entry": async_redact_data(entry.as_dict(), TO_REDACT),
        "device_info": {
            "name": wrapper.name,
            "model": wrapper.model,
            "sw_version": wrapper.sw_version,
        },
    }
