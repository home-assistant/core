"""Diagnostics support for Shelly."""
from __future__ import annotations

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from . import BlockDeviceWrapper, RpcDeviceWrapper
from .const import BLOCK, DATA_CONFIG_ENTRY, DOMAIN, RPC

TO_REDACT = {CONF_USERNAME, CONF_PASSWORD}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict:
    """Return diagnostics for a config entry."""
    data: dict = hass.data[DOMAIN][DATA_CONFIG_ENTRY][entry.entry_id]

    device_settings: str | dict = "not initialized"
    device_info: str | dict = "not initialized"
    if BLOCK in data:
        block_wrapper: BlockDeviceWrapper = data[BLOCK]
        if block_wrapper.device.initialized:
            device_settings = {
                k: v
                for k, v in block_wrapper.device.settings.items()
                if k in ["cloud", "coiot"]
            }
            device_info = {
                "name": block_wrapper.name,
                "model": block_wrapper.model,
                "sw_version": block_wrapper.sw_version,
            }
    else:
        rpc_wrapper: RpcDeviceWrapper = data[RPC]
        if rpc_wrapper.device.initialized:
            device_settings = {
                k: v for k, v in rpc_wrapper.device.config.items() if k in ["cloud"]
            }
            device_info = {
                "name": rpc_wrapper.name,
                "model": rpc_wrapper.model,
                "sw_version": rpc_wrapper.sw_version,
            }

    return {
        "entry": async_redact_data(entry.as_dict(), TO_REDACT),
        "device_info": device_info,
        "device_settings": device_settings,
    }
