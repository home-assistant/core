"""Diagnostics support for Amazon Devices integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_NAME, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .coordinator import AmazonConfigEntry

TO_REDACT = {CONF_PASSWORD, CONF_USERNAME, CONF_NAME, "title"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: AmazonConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""

    coordinator = entry.runtime_data

    devices: list[dict[str, dict[str, Any]]] = [
        {
            device.serial_number: {
                "account name": device.account_name,
                "capabilities": device.capabilities,
                "device family": device.device_family,
                "device type": device.device_type,
                "device cluster members": device.device_cluster_members,
                "online": device.online,
                "serial number": device.serial_number,
                "software version": device.software_version,
                "do not disturb": device.do_not_disturb,
                "response style": device.response_style,
                "bluetooth state": device.bluetooth_state,
            }
        }
        for device in coordinator.data.values()
    ]

    return {
        "entry": async_redact_data(entry.as_dict(), TO_REDACT),
        "device_info": {
            "last_update success": coordinator.last_update_success,
            "last_exception": repr(coordinator.last_exception),
            "devices": devices,
        },
    }
