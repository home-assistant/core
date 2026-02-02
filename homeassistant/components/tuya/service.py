"""Services for Tuya integration."""

from __future__ import annotations

from functools import partial
from typing import Any

from tuya_sharing import CustomerDevice, Manager
import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
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


async def _get_meal_plan_data_handler(
    hass: HomeAssistant, call: ServiceCall
) -> dict[str, Any]:
    """Handle get_meal_plan_data service call."""
    device, _ = _get_tuya_device(hass, call.data["device_id"])

    data = device.status.get("meal_plan")
    if data is None:
        raise HomeAssistantError(
            f"Device {device.name} does not have data for meal_plan. "
        )

    return {"data": data}


async def _set_meal_plan_data_handler(
    hass: HomeAssistant, call: ServiceCall
) -> dict[str, Any]:
    """Handle set_meal_plan_data service call."""
    device, manager = _get_tuya_device(hass, call.data["device_id"])
    data_value = call.data["data"]

    # Check if the device has this DP code in its function
    if "meal_plan" not in device.function:
        raise HomeAssistantError(f"Device {device.name} does not support meal_plan. ")
    commands = [{"code": "meal_plan", "value": data_value}]

    # Send the command using the manager
    await hass.async_add_executor_job(manager.send_commands, device.id, commands)

    return {
        "success": True,
        "device": device.name,
        "value": data_value,
    }


async def async_register_services(hass: HomeAssistant) -> None:
    """Register Tuya services."""
    # Register get_meal_plan_data service
    hass.services.async_register(
        DOMAIN,
        "get_meal_plan_data",
        partial(_get_meal_plan_data_handler, hass),
        schema=vol.Schema(
            {
                vol.Required("device_id"): str,
            }
        ),
        supports_response=SupportsResponse.ONLY,
    )

    # Register set_meal_plan_data service
    hass.services.async_register(
        DOMAIN,
        "set_meal_plan_data",
        partial(_set_meal_plan_data_handler, hass),
        schema=vol.Schema(
            {
                vol.Required("device_id"): str,
                vol.Required("data"): vol.Any(str),
            }
        ),
        supports_response=SupportsResponse.OPTIONAL,
    )
