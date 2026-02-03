"""Services for Tuya integration."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from tuya_sharing import CustomerDevice, Manager
import voluptuous as vol

from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN
from .device_quirks import days_bitmap_to_names, days_names_to_bitmap, serializer

FEEDING_ENTRY_SCHEMA = vol.Schema(
    {
        vol.Optional("days"): [vol.All(int, vol.Range(min=0, max=6))],
        vol.Required("hour"): int,
        vol.Required("minute"): int,
        vol.Required("portion"): int,
        vol.Required("enabled"): int,
    }
)


class Service(StrEnum):
    """Tuya services."""

    GET_MEAL_PLAN_DATA = "get_meal_plan_data"
    SET_MEAL_PLAN_DATA = "set_meal_plan_data"


def _get_tuya_device(
    hass: HomeAssistant, device_id: str
) -> tuple[CustomerDevice, Manager]:
    """Get a Tuya device and manager from a Home Assistant device registry ID."""
    device_registry = dr.async_get(hass)
    device_entry = device_registry.async_get(device_id)
    if device_entry is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="device_not_found",
            translation_placeholders={
                "device_id": device_id,
            },
        )

    # Find the Tuya device ID from identifiers
    tuya_device_id = None
    for identifier_domain, identifier_value in device_entry.identifiers:
        if identifier_domain == DOMAIN:
            tuya_device_id = identifier_value
            break

    if tuya_device_id is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="device_not_tuya_device",
            translation_placeholders={
                "device_id": device_id,
            },
        )

    # Find the device in Tuya config entry
    for entry in hass.config_entries.async_entries(DOMAIN):
        manager = entry.runtime_data.manager
        if tuya_device_id in manager.device_map:
            return manager.device_map[tuya_device_id], manager

    raise ServiceValidationError(
        translation_domain=DOMAIN,
        translation_key="device_not_found",
        translation_placeholders={
            "device_id": device_id,
        },
    )


async def async_get_meal_plan_data(call: ServiceCall) -> dict[str, Any]:
    """Handle get_meal_plan_data service call."""
    device, _ = _get_tuya_device(call.hass, call.data[ATTR_DEVICE_ID])

    data = device.status.get("meal_plan")
    if data is None:
        raise ServiceValidationError(
            f"Device {device.name} does not have data for meal_plan. "
        )

    return {"data": days_bitmap_to_names(serializer(device).decode(data))}


async def async_set_meal_plan_data(call: ServiceCall) -> None:
    """Handle set_meal_plan_data service call."""
    device, manager = _get_tuya_device(call.hass, call.data[ATTR_DEVICE_ID])

    # Check if the device has this DP code in its function
    if "meal_plan" not in device.function:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="device_not_support_meal_plan",
            translation_placeholders={
                "device_id": device.id,
            },
        )
    converted_data = days_names_to_bitmap(call.data["data"])
    commands = [
        {
            "code": "meal_plan",
            "value": serializer(device).encode(converted_data),
        }
    ]

    # Send the command using the manager
    await call.hass.async_add_executor_job(manager.send_commands, device.id, commands)


async def async_setup_services(hass: HomeAssistant) -> None:
    """Set up Tuya services."""

    hass.services.async_register(
        DOMAIN,
        Service.GET_MEAL_PLAN_DATA,
        async_get_meal_plan_data,
        schema=vol.Schema(
            {
                vol.Required("device_id"): str,
            }
        ),
        supports_response=SupportsResponse.ONLY,
    )

    hass.services.async_register(
        DOMAIN,
        Service.SET_MEAL_PLAN_DATA,
        async_set_meal_plan_data,
        schema=vol.Schema(
            {
                vol.Required("device_id"): str,
                vol.Required("data"): vol.All(
                    list,
                    [FEEDING_ENTRY_SCHEMA],
                ),
            }
        ),
    )
