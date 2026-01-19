"""Support for BSB-Lan services."""

from __future__ import annotations

from datetime import time
import logging
from typing import TYPE_CHECKING

from bsblan import BSBLANError, DaySchedule, DHWSchedule, TimeSlot
import voluptuous as vol

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.util import dt as dt_util

from .const import DOMAIN

if TYPE_CHECKING:
    from . import BSBLanConfigEntry

LOGGER = logging.getLogger(__name__)

ATTR_DEVICE_ID = "device_id"
ATTR_MONDAY_SLOTS = "monday_slots"
ATTR_TUESDAY_SLOTS = "tuesday_slots"
ATTR_WEDNESDAY_SLOTS = "wednesday_slots"
ATTR_THURSDAY_SLOTS = "thursday_slots"
ATTR_FRIDAY_SLOTS = "friday_slots"
ATTR_SATURDAY_SLOTS = "saturday_slots"
ATTR_SUNDAY_SLOTS = "sunday_slots"

# Service names
SERVICE_SET_HOT_WATER_SCHEDULE = "set_hot_water_schedule"
SERVICE_SYNC_TIME = "sync_time"


# Schema for a single time slot
_SLOT_SCHEMA = vol.Schema(
    {
        vol.Required("start_time"): cv.time,
        vol.Required("end_time"): cv.time,
    }
)


SERVICE_SET_HOT_WATER_SCHEDULE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): cv.string,
        vol.Optional(ATTR_MONDAY_SLOTS): vol.All(cv.ensure_list, [_SLOT_SCHEMA]),
        vol.Optional(ATTR_TUESDAY_SLOTS): vol.All(cv.ensure_list, [_SLOT_SCHEMA]),
        vol.Optional(ATTR_WEDNESDAY_SLOTS): vol.All(cv.ensure_list, [_SLOT_SCHEMA]),
        vol.Optional(ATTR_THURSDAY_SLOTS): vol.All(cv.ensure_list, [_SLOT_SCHEMA]),
        vol.Optional(ATTR_FRIDAY_SLOTS): vol.All(cv.ensure_list, [_SLOT_SCHEMA]),
        vol.Optional(ATTR_SATURDAY_SLOTS): vol.All(cv.ensure_list, [_SLOT_SCHEMA]),
        vol.Optional(ATTR_SUNDAY_SLOTS): vol.All(cv.ensure_list, [_SLOT_SCHEMA]),
    }
)


def _convert_time_slots_to_day_schedule(
    slots: list[dict[str, time]] | None,
) -> DaySchedule | None:
    """Convert list of time slot dicts to a DaySchedule object.

    Example: [{"start_time": time(6, 0), "end_time": time(8, 0)},
              {"start_time": time(17, 0), "end_time": time(21, 0)}]
    becomes: DaySchedule with two TimeSlot objects

    None returns None (don't modify this day).
    Empty list returns DaySchedule with empty slots (clear this day).
    """
    if slots is None:
        return None

    if not slots:
        return DaySchedule(slots=[])

    time_slots = []
    for slot in slots:
        start_time = slot["start_time"]
        end_time = slot["end_time"]

        # Validate that end time is after start time
        if end_time <= start_time:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="end_time_before_start_time",
                translation_placeholders={
                    "start_time": start_time.strftime("%H:%M"),
                    "end_time": end_time.strftime("%H:%M"),
                },
            )

        time_slots.append(TimeSlot(start=start_time, end=end_time))
        LOGGER.debug(
            "Created time slot: %s-%s",
            start_time.strftime("%H:%M"),
            end_time.strftime("%H:%M"),
        )

    LOGGER.debug("Created DaySchedule with %d slots", len(time_slots))
    return DaySchedule(slots=time_slots)


async def set_hot_water_schedule(service_call: ServiceCall) -> None:
    """Set hot water heating schedule."""
    device_id = service_call.data[ATTR_DEVICE_ID]

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
    matching_entries: list[BSBLanConfigEntry] = [
        entry
        for entry in service_call.hass.config_entries.async_entries(DOMAIN)
        if entry.entry_id in device_entry.config_entries
    ]

    if not matching_entries:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="no_config_entry_for_device",
            translation_placeholders={"device_id": device_entry.name or device_id},
        )

    entry = matching_entries[0]

    # Verify the config entry is loaded
    if entry.state is not ConfigEntryState.LOADED:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="config_entry_not_loaded",
            translation_placeholders={"device_name": device_entry.name or device_id},
        )

    client = entry.runtime_data.client

    # Convert time slots to DaySchedule objects
    monday = _convert_time_slots_to_day_schedule(
        service_call.data.get(ATTR_MONDAY_SLOTS)
    )
    tuesday = _convert_time_slots_to_day_schedule(
        service_call.data.get(ATTR_TUESDAY_SLOTS)
    )
    wednesday = _convert_time_slots_to_day_schedule(
        service_call.data.get(ATTR_WEDNESDAY_SLOTS)
    )
    thursday = _convert_time_slots_to_day_schedule(
        service_call.data.get(ATTR_THURSDAY_SLOTS)
    )
    friday = _convert_time_slots_to_day_schedule(
        service_call.data.get(ATTR_FRIDAY_SLOTS)
    )
    saturday = _convert_time_slots_to_day_schedule(
        service_call.data.get(ATTR_SATURDAY_SLOTS)
    )
    sunday = _convert_time_slots_to_day_schedule(
        service_call.data.get(ATTR_SUNDAY_SLOTS)
    )

    # Create the DHWSchedule object
    dhw_schedule = DHWSchedule(
        monday=monday,
        tuesday=tuesday,
        wednesday=wednesday,
        thursday=thursday,
        friday=friday,
        saturday=saturday,
        sunday=sunday,
    )

    LOGGER.debug(
        "Setting hot water schedule - Monday: %s, Tuesday: %s, Wednesday: %s, "
        "Thursday: %s, Friday: %s, Saturday: %s, Sunday: %s",
        monday,
        tuesday,
        wednesday,
        thursday,
        friday,
        saturday,
        sunday,
    )

    try:
        # Call the BSB-Lan API to set the schedule
        await client.set_hot_water_schedule(dhw_schedule)
    except BSBLANError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="set_schedule_failed",
            translation_placeholders={"error": str(err)},
        ) from err

    # Refresh the slow coordinator to get the updated schedule
    await entry.runtime_data.slow_coordinator.async_request_refresh()


async def async_sync_time(service_call: ServiceCall) -> None:
    """Synchronize BSB-LAN device time with Home Assistant."""
    device_id: str = service_call.data[ATTR_DEVICE_ID]

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
    matching_entries: list[BSBLanConfigEntry] = [
        entry
        for entry in service_call.hass.config_entries.async_entries(DOMAIN)
        if entry.entry_id in device_entry.config_entries
    ]

    if not matching_entries:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="no_config_entry_for_device",
            translation_placeholders={"device_id": device_entry.name or device_id},
        )

    entry = matching_entries[0]

    # Verify the config entry is loaded
    if entry.state is not ConfigEntryState.LOADED:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="config_entry_not_loaded",
            translation_placeholders={"device_name": device_entry.name or device_id},
        )

    client = entry.runtime_data.client

    try:
        # Get current device time
        device_time = await client.time()
        current_time = dt_util.now()
        current_time_str = current_time.strftime("%d.%m.%Y %H:%M:%S")

        # Only sync if device time differs from HA time
        if device_time.time.value != current_time_str:
            await client.set_time(current_time_str)
    except BSBLANError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="sync_time_failed",
            translation_placeholders={
                "device_name": device_entry.name or device_id,
                "error": str(err),
            },
        ) from err


SYNC_TIME_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): cv.string,
    }
)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the BSB-Lan services."""
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_HOT_WATER_SCHEDULE,
        set_hot_water_schedule,
        schema=SERVICE_SET_HOT_WATER_SCHEDULE_SCHEMA,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_SYNC_TIME,
        async_sync_time,
        schema=SYNC_TIME_SCHEMA,
    )
