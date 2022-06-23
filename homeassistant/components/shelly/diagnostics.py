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
    device_status: str | dict = "not initialized"
    if BLOCK in data:
        block_wrapper: BlockDeviceWrapper = data[BLOCK]
        device_info = {
            "name": block_wrapper.name,
            "model": block_wrapper.model,
            "sw_version": block_wrapper.sw_version,
        }
        if block_wrapper.device.initialized:
            device_settings = {
                k: v
                for k, v in block_wrapper.device.settings.items()
                if k in ["cloud", "coiot"]
            }
            device_status = {
                k: v
                for k, v in block_wrapper.device.status.items()
                if k
                in [
                    "update",
                    "wifi_sta",
                    "time",
                    "has_update",
                    "ram_total",
                    "ram_free",
                    "ram_lwm",
                    "fs_size",
                    "fs_free",
                    "uptime",
                ]
            }
    else:
        rpc_wrapper: RpcDeviceWrapper = data[RPC]
        device_info = {
            "name": rpc_wrapper.name,
            "model": rpc_wrapper.model,
            "sw_version": rpc_wrapper.sw_version,
        }
        if rpc_wrapper.device.initialized:
            device_settings = {
                k: v for k, v in rpc_wrapper.device.config.items() if k in ["cloud"]
            }
            device_status = {
                k: v
                for k, v in rpc_wrapper.device.status.items()
                if k in ["sys", "wifi"]
            }

    if isinstance(device_status, dict):
        device_status = async_redact_data(device_status, ["ssid"])

    return {
        "entry": async_redact_data(entry.as_dict(), TO_REDACT),
        "device_info": device_info,
        "device_settings": device_settings,
        "device_status": device_status,
    }
