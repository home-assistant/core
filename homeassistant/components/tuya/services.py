"""Services for Tuya integration."""

from enum import StrEnum
from typing import Any

from tuya_device_handlers.device_wrapper.service_feeder_schedule import (
    FeederSchedule,
    get_feeder_schedule_wrapper,
)
from tuya_sharing import CustomerDevice, Manager
import voluptuous as vol

from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN

DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]

FEEDING_ENTRY_SCHEMA = vol.Schema(
    {
        vol.Optional("days"): [vol.In(DAYS)],
        vol.Required("time"): str,
        vol.Required("portion"): int,
        vol.Required("enabled"): bool,
    }
)


class Service(StrEnum):
    """Tuya services."""

    GET_FEEDER_MEAL_PLAN = "get_feeder_meal_plan"
    SET_FEEDER_MEAL_PLAN = "set_feeder_meal_plan"


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
    for entry in hass.config_entries.async_loaded_entries(DOMAIN):
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


async def async_get_feeder_meal_plan(
    call: ServiceCall,
) -> dict[str, Any]:
    """Handle get_feeder_meal_plan service call."""
    device, _ = _get_tuya_device(call.hass, call.data[ATTR_DEVICE_ID])

    if not (wrapper := get_feeder_schedule_wrapper(device)):
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="device_not_support_meal_plan_status",
            translation_placeholders={
                "device_id": device.id,
            },
        )

    meal_plan = wrapper.read_device_status(device)
    if meal_plan is None:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="invalid_meal_plan_data",
        )

    return {"meal_plan": meal_plan}


async def async_set_feeder_meal_plan(call: ServiceCall) -> None:
    """Handle set_feeder_meal_plan service call."""
    device, manager = _get_tuya_device(call.hass, call.data[ATTR_DEVICE_ID])

    if not (wrapper := get_feeder_schedule_wrapper(device)):
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="device_not_support_meal_plan_function",
            translation_placeholders={
                "device_id": device.id,
            },
        )

    meal_plan: list[FeederSchedule] = call.data["meal_plan"]

    await call.hass.async_add_executor_job(
        manager.send_commands,
        device.id,
        wrapper.get_update_commands(device, meal_plan),
    )


async def async_setup_services(hass: HomeAssistant) -> None:
    """Set up Tuya services."""

    hass.services.async_register(
        DOMAIN,
        Service.GET_FEEDER_MEAL_PLAN,
        async_get_feeder_meal_plan,
        schema=vol.Schema(
            {
                vol.Required(ATTR_DEVICE_ID): str,
            }
        ),
        supports_response=SupportsResponse.ONLY,
    )

    hass.services.async_register(
        DOMAIN,
        Service.SET_FEEDER_MEAL_PLAN,
        async_set_feeder_meal_plan,
        schema=vol.Schema(
            {
                vol.Required(ATTR_DEVICE_ID): str,
                vol.Required("meal_plan"): vol.All(
                    list,
                    [FEEDING_ENTRY_SCHEMA],
                ),
            }
        ),
    )
