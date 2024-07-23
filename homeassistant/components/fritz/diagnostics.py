"""Diagnostics support for AVM FRITZ!Box."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .common import AvmWrapper
from .const import DOMAIN

TO_REDACT = {CONF_USERNAME, CONF_PASSWORD}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    avm_wrapper: AvmWrapper = hass.data[DOMAIN][entry.entry_id]

    return {
        "entry": async_redact_data(entry.as_dict(), TO_REDACT),
        "device_info": {
            "model": avm_wrapper.model,
            "unique_id": avm_wrapper.unique_id.replace(
                avm_wrapper.unique_id[6:11], "XX:XX"
            ),
            "current_firmware": avm_wrapper.current_firmware,
            "latest_firmware": avm_wrapper.latest_firmware,
            "update_available": avm_wrapper.update_available,
            "connection_type": avm_wrapper.device_conn_type,
            "is_router": avm_wrapper.device_is_router,
            "mesh_role": avm_wrapper.mesh_role,
            "last_update success": avm_wrapper.last_update_success,
            "last_exception": avm_wrapper.last_exception,
            "discovered_services": list(avm_wrapper.connection.services),
            "client_devices": [
                {
                    "connected_to": device.connected_to,
                    "connection_type": device.connection_type,
                    "hostname": device.hostname,
                    "is_connected": device.is_connected,
                    "last_activity": device.last_activity,
                    "wan_access": device.wan_access,
                }
                for _, device in avm_wrapper.devices.items()
            ],
            "wan_link_properties": await avm_wrapper.async_get_wan_link_properties(),
        },
    }
