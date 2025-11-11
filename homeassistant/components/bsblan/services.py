"""Support for BSB-Lan services."""

from __future__ import annotations

from datetime import time
import logging
from typing import TYPE_CHECKING

from bsblan import BSBLANError, DHWTimeSwitchPrograms

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
ATTR_STANDARD_VALUES_SLOTS = "standard_values_slots"

# Service name
SERVICE_SET_HOT_WATER_SCHEDULE = "set_hot_water_schedule"


def _convert_time_slots_to_string(slots: list[dict[str, time]] | None) -> str:
    """Convert list of time slot dicts to BSB-LAN format string.

    Example: [{"start_time": "06:00", "end_time": "08:00"}, {"start_time": "17:00", "end_time": "21:00"}]
    becomes: "06:00-08:00 17:00-21:00"

    Empty list or None returns empty string.
    """
    if slots is None or not slots:
        return ""

    time_periods = []
    for slot in slots:
        start = slot.get("start_time")
        end = slot.get("end_time")

        if start and end:
            # Convert time objects to HH:MM format (no seconds!)
            if isinstance(start, time):
                start_str = start.strftime("%H:%M")
                start_time_obj = start
            elif isinstance(start, str):
                # If it's already a string, strip seconds if present
                start_str = start[:5] if len(start) >= 5 else start
                # Parse string to time object for validation
                try:
                    parts = start.split(":")
                    start_time_obj = time(int(parts[0]), int(parts[1]))
                except (ValueError, IndexError):
                    raise ServiceValidationError(
                        translation_domain=DOMAIN,
                        translation_key="invalid_time_format",
                    ) from None
            else:
                start_str = str(start)
                start_time_obj = None

            if isinstance(end, time):
                end_str = end.strftime("%H:%M")
                end_time_obj = end
            elif isinstance(end, str):
                # If it's already a string, strip seconds if present
                end_str = end[:5] if len(end) >= 5 else end
                # Parse string to time object for validation
                try:
                    parts = end.split(":")
                    end_time_obj = time(int(parts[0]), int(parts[1]))
                except (ValueError, IndexError):
                    raise ServiceValidationError(
                        translation_domain=DOMAIN,
                        translation_key="invalid_time_format",
                    ) from None
            else:
                end_str = str(end)
                end_time_obj = None

            # Validate that end time is after start time
            if start_time_obj and end_time_obj and end_time_obj <= start_time_obj:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="end_time_before_start_time",
                    translation_placeholders={
                        "start_time": start_str,
                        "end_time": end_str,
                    },
                )

            time_periods.append(f"{start_str}-{end_str}")
            LOGGER.debug("Created time period: %s-%s", start_str, end_str)

    result = " ".join(time_periods) if time_periods else ""
    LOGGER.debug("Final converted string: %s", result)
    return result


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

    # Convert time slots to BSB-LAN format strings
    monday_str = _convert_time_slots_to_string(service_call.data.get(ATTR_MONDAY_SLOTS))
    tuesday_str = _convert_time_slots_to_string(
        service_call.data.get(ATTR_TUESDAY_SLOTS)
    )
    wednesday_str = _convert_time_slots_to_string(
        service_call.data.get(ATTR_WEDNESDAY_SLOTS)
    )
    thursday_str = _convert_time_slots_to_string(
        service_call.data.get(ATTR_THURSDAY_SLOTS)
    )
    friday_str = _convert_time_slots_to_string(service_call.data.get(ATTR_FRIDAY_SLOTS))
    saturday_str = _convert_time_slots_to_string(
        service_call.data.get(ATTR_SATURDAY_SLOTS)
    )
    sunday_str = _convert_time_slots_to_string(service_call.data.get(ATTR_SUNDAY_SLOTS))
    standard_values_str = _convert_time_slots_to_string(
        service_call.data.get(ATTR_STANDARD_VALUES_SLOTS)
    )

    # Create the DHWTimeSwitchPrograms object
    dhw_programs = DHWTimeSwitchPrograms(
        monday=monday_str,
        tuesday=tuesday_str,
        wednesday=wednesday_str,
        thursday=thursday_str,
        friday=friday_str,
        saturday=saturday_str,
        sunday=sunday_str,
        standard_values=standard_values_str,
    )

    LOGGER.debug(
        "Setting hot water schedule - Monday: %s, Tuesday: %s, Wednesday: %s, "
        "Thursday: %s, Friday: %s, Saturday: %s, Sunday: %s, Standard: %s",
        monday_str,
        tuesday_str,
        wednesday_str,
        thursday_str,
        friday_str,
        saturday_str,
        sunday_str,
        standard_values_str,
    )

    try:
        # Call the BSB-Lan API to set the schedule
        await client.set_hot_water(dhw_time_programs=dhw_programs)
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
