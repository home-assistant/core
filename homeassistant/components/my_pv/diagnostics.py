"""Diagnostics support for the my-PV integration."""

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_HOST, CONF_PASSWORD
from homeassistant.core import HomeAssistant

from .coordinator import MyPVConfigEntry

TO_REDACT = {CONF_HOST, CONF_PASSWORD, "mac_address", "serial_number"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: MyPVConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    device = entry.runtime_data.device

    diagnostics: dict[str, Any] = {
        "entry_data": dict(entry.data),
        "device": {
            "model": device.model,
            "serial_number": device.serial_number,
            # The prefix identifies the device type and configuration, not the device
            "serial_number_prefix": device.serial_number[:6],
            "mac_address": device.mac_address,
            "hardware_version": device.hardware_version,
            "firmware_version": device.firmware_version,
            "connected": device.connected,
        },
        "setup_configurations": device.get_setup_configurations(),
        "data_configurations": device.get_data_configurations(),
    }

    # The device raises an error when reading values while not connected
    if device.connected:
        diagnostics["setup_values"] = {
            key: device.get_setup_value(key)
            for key in diagnostics["setup_configurations"]
        }
        diagnostics["data_values"] = {
            key: device.get_data_value(key)
            for key in diagnostics["data_configurations"]
        }

    return async_redact_data(diagnostics, TO_REDACT)
