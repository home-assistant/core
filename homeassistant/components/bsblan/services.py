"""Support for BSB-Lan services."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from bsblan import DHWTimeSwitchPrograms
import voluptuous as vol

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv, device_registry as dr

from .const import DOMAIN

if TYPE_CHECKING:
    from . import BSBLanConfigEntry

LOGGER = logging.getLogger(__name__)

ATTR_DEVICE = "device"
ATTR_SCHEDULE = "schedule"

# Service name
SERVICE_SET_HOT_WATER_SCHEDULE = "set_hot_water_schedule"

# Schema for the day schedule
SERVICE_SCHEDULE_DAY_SCHEMA = vol.Schema(cv.string)

# Schema for the complete schedule
SERVICE_SCHEDULE_SCHEMA = vol.Schema(
    {
        vol.Optional("monday"): vol.Any(None, SERVICE_SCHEDULE_DAY_SCHEMA),
        vol.Optional("tuesday"): vol.Any(None, SERVICE_SCHEDULE_DAY_SCHEMA),
        vol.Optional("wednesday"): vol.Any(None, SERVICE_SCHEDULE_DAY_SCHEMA),
        vol.Optional("thursday"): vol.Any(None, SERVICE_SCHEDULE_DAY_SCHEMA),
        vol.Optional("friday"): vol.Any(None, SERVICE_SCHEDULE_DAY_SCHEMA),
        vol.Optional("saturday"): vol.Any(None, SERVICE_SCHEDULE_DAY_SCHEMA),
        vol.Optional("sunday"): vol.Any(None, SERVICE_SCHEDULE_DAY_SCHEMA),
        vol.Optional("standard_values"): vol.Any(None, SERVICE_SCHEDULE_DAY_SCHEMA),
    }
)

# Schema for the service call
SERVICE_SET_HOT_WATER_SCHEDULE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE): cv.string,
        vol.Required(ATTR_SCHEDULE): SERVICE_SCHEDULE_SCHEMA,
    }
)


async def set_hot_water_schedule(service_call: ServiceCall) -> None:
    """Set hot water heating schedule."""
    schedule_data: dict[str, Any] = service_call.data[ATTR_SCHEDULE]
    device_id = service_call.data[ATTR_DEVICE]

    # Get the device and config entry
    device_registry = dr.async_get(service_call.hass)
    device_entry = device_registry.async_get(device_id)

    if device_entry is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="invalid_device_id",
            translation_placeholders={"device_id": device_id},
        )

    # Find the config entry for this device
    loaded_entries: list[BSBLanConfigEntry] = [
        entry
        for entry in service_call.hass.config_entries.async_loaded_entries(DOMAIN)
        if entry.entry_id in device_entry.config_entries
    ]

    if not loaded_entries:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="no_config_entry_for_device",
            translation_placeholders={"device_id": device_entry.name or device_id},
        )

    entry = loaded_entries[0]

    # Verify the config entry is loaded
    if entry.state is not ConfigEntryState.LOADED:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="config_entry_not_loaded",
            translation_placeholders={"device_name": device_entry.name or device_id},
        )

    client = entry.runtime_data.client

    # Create the DHWTimeSwitchPrograms object
    dhw_programs = DHWTimeSwitchPrograms(
        monday=schedule_data.get("monday"),
        tuesday=schedule_data.get("tuesday"),
        wednesday=schedule_data.get("wednesday"),
        thursday=schedule_data.get("thursday"),
        friday=schedule_data.get("friday"),
        saturday=schedule_data.get("saturday"),
        sunday=schedule_data.get("sunday"),
        standard_values=schedule_data.get("standard_values"),
    )

    LOGGER.debug("Setting hot water schedule: %s", schedule_data)

    try:
        # Call the BSB-Lan API to set the schedule
        await client.set_hot_water(dhw_time_programs=dhw_programs)
    except Exception as err:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="set_schedule_failed",
            translation_placeholders={"error": str(err)},
        ) from err

    LOGGER.info("Hot water schedule updated successfully")

    # Refresh the slow coordinator to get the updated schedule
    await entry.runtime_data.slow_coordinator.async_request_refresh()


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the BSB-Lan services."""
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_HOT_WATER_SCHEDULE,
        set_hot_water_schedule,
        schema=SERVICE_SET_HOT_WATER_SCHEDULE_SCHEMA,
    )


@callback
def async_unload_services(hass: HomeAssistant) -> None:
    """Unload BSB-Lan services."""
    hass.services.async_remove(DOMAIN, SERVICE_SET_HOT_WATER_SCHEDULE)
