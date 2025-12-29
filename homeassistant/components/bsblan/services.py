"""Support for BSB-Lan services."""

from __future__ import annotations

from datetime import time
import logging
from typing import TYPE_CHECKING

from bsblan import BSBLANError, DaySchedule, DHWSchedule, TimeSlot

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr

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

# Service name
SERVICE_SET_HOT_WATER_SCHEDULE = "set_hot_water_schedule"


def _parse_time_value(value: time | str) -> time:
    """Parse a time value from either a time object or string.

    Raises ServiceValidationError if the format is invalid.
    """
    if isinstance(value, time):
        return value

    if isinstance(value, str):
        try:
            parts = value.split(":")
            return time(int(parts[0]), int(parts[1]))
        except (ValueError, IndexError):
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_time_format",
            ) from None

    raise ServiceValidationError(
        translation_domain=DOMAIN,
        translation_key="invalid_time_format",
    )


def _convert_time_slots_to_day_schedule(
    slots: list[dict[str, time]] | None,
) -> DaySchedule | None:
    """Convert list of time slot dicts to a DaySchedule object.

    Example: [{"start_time": "06:00", "end_time": "08:00"},
              {"start_time": "17:00", "end_time": "21:00"}]
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
        start = slot.get("start_time")
        end = slot.get("end_time")

        if start and end:
            start_time = _parse_time_value(start)
            end_time = _parse_time_value(end)

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


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the BSB-Lan services."""
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_HOT_WATER_SCHEDULE,
        set_hot_water_schedule,
    )
