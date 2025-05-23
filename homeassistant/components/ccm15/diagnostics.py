"""Diagnostics support for CCM15."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from .coordinator import CCM15ConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: CCM15ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = config_entry.runtime_data

    return {
        str(device_id): {
            "is_celsius": device.is_celsius,
            "locked_cool_temperature": device.locked_cool_temperature,
            "locked_heat_temperature": device.locked_heat_temperature,
            "locked_ac_mode": device.locked_ac_mode,
            "error_code": device.error_code,
            "ac_mode": device.ac_mode,
            "fan_mode": device.fan_mode,
            "is_ac_mode_locked": device.is_ac_mode_locked,
            "temperature_setpoint": device.temperature_setpoint,
            "fan_locked": device.fan_locked,
            "is_remote_locked": device.is_remote_locked,
            "temperature": device.temperature,
        }
        for device_id, device in coordinator.data.devices.items()
    }
