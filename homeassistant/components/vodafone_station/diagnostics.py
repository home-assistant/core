"""Diagnostics support for Vodafone Station."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import VodafoneStationRouter

TO_REDACT = {CONF_USERNAME, CONF_PASSWORD}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""

    coordinator: VodafoneStationRouter = hass.data[DOMAIN][entry.entry_id]

    sensors_data = coordinator.data.sensors
    return {
        "entry": async_redact_data(entry.as_dict(), TO_REDACT),
        "device_info": {
            "sys_model_name": sensors_data.get("sys_model_name"),
            "sys_firmware_version": sensors_data["sys_firmware_version"],
            "sys_hardware_version": sensors_data["sys_hardware_version"],
            "sys_cpu_usage": sensors_data["sys_cpu_usage"][:-1],
            "sys_memory_usage": sensors_data["sys_memory_usage"][:-1],
            "sys_reboot_cause": sensors_data["sys_reboot_cause"],
            "last_update success": coordinator.last_update_success,
            "last_exception": coordinator.last_exception,
            "client_devices": [
                {
                    "hostname": device_info.device.name,
                    "connection_type": device_info.device.connection_type,
                    "connected": device_info.device.connected,
                    "type": device_info.device.type,
                }
                for _, device_info in coordinator.data.devices.items()
            ],
        },
    }
