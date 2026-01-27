"""Services for Tuya integration."""

from __future__ import annotations

from functools import partial
from typing import Any

from tuya_sharing import CustomerDevice, Manager
import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN


def _get_tuya_device(
    hass: HomeAssistant, device_id: str
) -> tuple[CustomerDevice, Manager]:
    """Get a Tuya device and manager from a Home Assistant device registry ID."""
    device_registry = dr.async_get(hass)
    device_entry = device_registry.async_get(device_id)
    if device_entry is None:
        raise HomeAssistantError(f"Device {device_id} not found")

    # Find the Tuya device ID from identifiers
    tuya_device_id = None
    for identifier_domain, identifier_value in device_entry.identifiers:
        if identifier_domain == DOMAIN:
            tuya_device_id = identifier_value
            break

    if tuya_device_id is None:
        raise HomeAssistantError(f"Device {device_id} is not a Tuya device")

    # Find the device in Tuya config entry
    for entry in hass.config_entries.async_entries(DOMAIN):
        manager = entry.runtime_data.manager
        if tuya_device_id in manager.device_map:
            return manager.device_map[tuya_device_id], manager

    raise HomeAssistantError(f"Tuya device {tuya_device_id} not found")


async def _get_data_handler(hass: HomeAssistant, call: ServiceCall) -> dict[str, Any]:
    """Handle get_data service call."""
    device, _ = _get_tuya_device(hass, call.data["device_id"])
    dp_code = call.data["dp_code"]

    data = device.status.get(dp_code)
    if data is None:
        raise HomeAssistantError(
            f"Device {device.name} does not have data for DP code '{dp_code}'. "
            f"Available codes: {', '.join(device.status.keys())}"
        )

    return {"data": data}


async def _set_data_handler(hass: HomeAssistant, call: ServiceCall) -> dict[str, Any]:
    """Handle set_data service call."""
    device, manager = _get_tuya_device(hass, call.data["device_id"])
    dp_code = call.data["dp_code"]
    data_value = call.data["data"]

    # Check if the device has this DP code in its function
    if dp_code not in device.function:
        raise HomeAssistantError(
            f"Device {device.name} does not support DP code '{dp_code}'. "
            f"Available codes: {', '.join(device.function.keys())}"
        )
    commands = [{"code": dp_code, "value": data_value}]

    # Send the command using the manager
    await hass.async_add_executor_job(manager.send_commands, device.id, commands)

    return {
        "success": True,
        "device": device.name,
        "dp_code": dp_code,
        "value": data_value,
    }


async def _get_available_dp_codes_handler(
    hass: HomeAssistant, call: ServiceCall
) -> dict[str, Any]:
    """Handle get_available_dp_codes service call."""
    device, _ = _get_tuya_device(hass, call.data["device_id"])

    # Return both settable (function) and readable (status) codes with current values
    settable_codes = list(device.function.keys())
    readable_codes = list(device.status.keys())

    # Include current values for readable codes
    current_values = {code: device.status.get(code) for code in readable_codes}

    return {
        "settable_codes": settable_codes,
        "readable_codes": readable_codes,
        "current_values": current_values,
    }


async def async_register_services(hass: HomeAssistant) -> None:
    """Register Tuya services."""
    # Register get_data service
    hass.services.async_register(
        DOMAIN,
        "get_data",
        partial(_get_data_handler, hass),
        schema=vol.Schema(
            {
                vol.Required("device_id"): str,
                vol.Required("dp_code"): str,
            }
        ),
        supports_response="only",
    )

    # Register set_data service
    hass.services.async_register(
        DOMAIN,
        "set_data",
        partial(_set_data_handler, hass),
        schema=vol.Schema(
            {
                vol.Required("device_id"): str,
                vol.Required("dp_code"): str,
                vol.Required("data"): vol.Any(str, int, float, bool, dict, list),
            }
        ),
        supports_response="optional",
    )

    # Register get_available_dp_codes service
    hass.services.async_register(
        DOMAIN,
        "get_available_dp_codes",
        partial(_get_available_dp_codes_handler, hass),
        schema=vol.Schema(
            {
                vol.Required("device_id"): str,
            }
        ),
        supports_response="only",
    )
