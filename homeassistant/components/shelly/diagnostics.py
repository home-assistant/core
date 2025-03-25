"""Diagnostics support for Shelly."""

from __future__ import annotations

from typing import Any

from homeassistant.components.bluetooth import async_scanner_by_source
from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import (
    ATTR_MODEL,
    ATTR_NAME,
    ATTR_SW_VERSION,
    CONF_PASSWORD,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant

from .coordinator import ShellyConfigEntry
from .utils import get_rpc_ws_url

TO_REDACT = {CONF_USERNAME, CONF_PASSWORD}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ShellyConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    shelly_entry_data = entry.runtime_data

    device_settings: str | dict = "not initialized"
    device_status: str | dict = "not initialized"
    bluetooth: str | dict = "not initialized"
    last_error: str = "not initialized"

    if shelly_entry_data.block:
        block_coordinator = shelly_entry_data.block
        assert block_coordinator
        device_info = {
            ATTR_NAME: block_coordinator.name,
            ATTR_MODEL: block_coordinator.model,
            ATTR_SW_VERSION: block_coordinator.sw_version,
        }
        if block_coordinator.device.initialized:
            device_settings = {
                k: v
                for k, v in block_coordinator.device.settings.items()
                if k in ["cloud", "coiot"]
            }
            device_status = {
                k: v
                for k, v in block_coordinator.device.status.items()
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

        if block_coordinator.device.last_error:
            last_error = repr(block_coordinator.device.last_error)

    else:
        rpc_coordinator = shelly_entry_data.rpc
        assert rpc_coordinator
        device_info = {
            ATTR_NAME: rpc_coordinator.name,
            ATTR_MODEL: rpc_coordinator.model,
            ATTR_SW_VERSION: rpc_coordinator.sw_version,
        }
        if rpc_coordinator.device.initialized:
            device_settings = {
                k: v for k, v in rpc_coordinator.device.config.items() if k in ["cloud"]
            }
            if not (ws_config := rpc_coordinator.device.config.get("ws", {})):
                device_settings["ws_outbound"] = "not supported"
            if (ws_outbound_enabled := ws_config.get("enable")) is not None:
                device_settings["ws_outbound_enabled"] = ws_outbound_enabled
                if ws_outbound_enabled:
                    device_settings["ws_outbound_server_valid"] = bool(
                        ws_config["server"] == get_rpc_ws_url(hass)
                    )
            device_status = {
                k: v
                for k, v in rpc_coordinator.device.status.items()
                if k in ["sys", "wifi"]
            }

        if scanner := async_scanner_by_source(hass, rpc_coordinator.bluetooth_source):
            bluetooth = {
                "scanner": await scanner.async_diagnostics(),
            }

        if rpc_coordinator.device.last_error:
            last_error = repr(rpc_coordinator.device.last_error)

    if isinstance(device_status, dict):
        device_status = async_redact_data(device_status, ["ssid"])

    return {
        "entry": async_redact_data(entry.as_dict(), TO_REDACT),
        "device_info": device_info,
        "device_settings": device_settings,
        "device_status": device_status,
        "last_error": last_error,
        "bluetooth": bluetooth,
    }
