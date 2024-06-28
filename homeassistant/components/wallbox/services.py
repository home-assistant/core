"""Home Assistant component for accessing the Wallbox Portal API.

Service allows to control Wallbox schedules (set and get)."
"""

from collections.abc import Mapping
import logging
from typing import Any

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.helpers import config_validation as cv, device_registry as dr

from .const import DOMAIN
from .coordinator import WallboxCoordinator

ATTR_CHARGER_ID = "charger_id"

LOGGER = logging.getLogger(__name__)

ATTR_SCHEDULES = "schedules"

SERVICE_SCHEDULE_DAYS_SCHEMA = vol.Schema(
    {
        vol.Required("monday"): cv.boolean,
        vol.Required("tuesday"): cv.boolean,
        vol.Required("wednesday"): cv.boolean,
        vol.Required("thursday"): cv.boolean,
        vol.Required("friday"): cv.boolean,
        vol.Required("saturday"): cv.boolean,
        vol.Required("sunday"): cv.boolean,
    }
)

SERVICE_SCHEDULE_SCHEMA = vol.Schema(
    {
        vol.Required("id"): cv.positive_int,
        vol.Required("enable"): cv.boolean,
        vol.Required("start"): cv.string,
        vol.Required("stop"): cv.string,
        vol.Required("days"): vol.Any(None, SERVICE_SCHEDULE_DAYS_SCHEMA),
        vol.Optional("max_current"): cv.positive_int,
        vol.Optional("max_energy"): cv.positive_int,
    }
)

SERVICE_SCHEDULES_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CHARGER_ID): cv.string,
        vol.Required(ATTR_SCHEDULES): vol.All(
            cv.ensure_list, [SERVICE_SCHEDULE_SCHEMA]
        ),
    }
)

SERVICE_GET_SCHEDULES_SCHEMA = vol.Schema({vol.Required(ATTR_CHARGER_ID): cv.string})

SERVICE_GET_SCHEDULES = "get_schedules"
SERVICE_SET_SCHEDULES = "set_schedules"
SERVICES = [SERVICE_GET_SCHEDULES, SERVICE_SET_SCHEDULES]


def setup_services(hass: HomeAssistant) -> None:
    """Register the Wallbox services."""

    async def get_schedules(service_call: ServiceCall) -> dict[str, Any]:
        coordinator = await get_coordinator(service_call.data)
        data = await coordinator.async_get_schedules()
        LOGGER.debug("schedules = {data}")
        return data

    async def set_schedules(service_call: ServiceCall) -> None:
        coordinator = await get_coordinator(service_call.data)
        await coordinator.async_set_schedules(service_call.data)

    async def get_coordinator(service_call_data: Mapping) -> WallboxCoordinator:
        device_registry = dr.async_get(hass)
        device_id = service_call_data[ATTR_CHARGER_ID]
        device_entry = device_registry.async_get_device({(DOMAIN, device_id)}, set())

        if device_entry is None:
            raise ValueError(f"Unable to find a charger with SN: {device_id}")

        coordinator: WallboxCoordinator = hass.data.get(DOMAIN, {})[
            device_entry.config_entries[0]  # only one config entry for the device
        ]

        if coordinator is None:
            raise ValueError(
                f"Unable to get coordinator for for charger with SN: {device_id}"
            )

        return coordinator

    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_SCHEDULES,
        get_schedules,
        schema=SERVICE_GET_SCHEDULES_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )

    hass.services.async_register(
        DOMAIN, SERVICE_SET_SCHEDULES, set_schedules, schema=SERVICE_SCHEDULES_SCHEMA
    )


def unload_services(hass: HomeAssistant) -> None:
    """Unload Wallbox services."""
    for service in SERVICES:
        hass.services.async_remove(DOMAIN, service)
