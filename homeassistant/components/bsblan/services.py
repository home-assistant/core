"""Support for BSB-LAN services."""

from datetime import time
import logging
from typing import TYPE_CHECKING, Any, Final

from bsblan import BSBLANError, DaySchedule, DHWSchedule, TimeSlot
import voluptuous as vol

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv, device_registry as dr

from .const import DOMAIN
from .helpers import async_sync_device_time

if TYPE_CHECKING:
    from . import BSBLanConfigEntry

LOGGER = logging.getLogger(__name__)

ATTR_MONDAY_SLOTS = "monday_slots"
ATTR_TUESDAY_SLOTS = "tuesday_slots"
ATTR_WEDNESDAY_SLOTS = "wednesday_slots"
ATTR_THURSDAY_SLOTS = "thursday_slots"
ATTR_FRIDAY_SLOTS = "friday_slots"
ATTR_SATURDAY_SLOTS = "saturday_slots"
ATTR_SUNDAY_SLOTS = "sunday_slots"

_DAY_NAME_SLOT_ATTR_PAIRS: tuple[tuple[str, str], ...] = (
    ("monday", ATTR_MONDAY_SLOTS),
    ("tuesday", ATTR_TUESDAY_SLOTS),
    ("wednesday", ATTR_WEDNESDAY_SLOTS),
    ("thursday", ATTR_THURSDAY_SLOTS),
    ("friday", ATTR_FRIDAY_SLOTS),
    ("saturday", ATTR_SATURDAY_SLOTS),
    ("sunday", ATTR_SUNDAY_SLOTS),
)


# Schema for a single time slot
_SLOT_SCHEMA = vol.Schema(
    {
        vol.Required("start_time"): cv.time,
        vol.Required("end_time"): cv.time,
    }
)


_WEEKLY_SCHEDULE_FIELDS: Final[dict[vol.Marker, Any]] = {
    vol.Optional(slot_attr): vol.All(cv.ensure_list, [_SLOT_SCHEMA])
    for _, slot_attr in _DAY_NAME_SLOT_ATTR_PAIRS
}


SERVICE_SET_HOT_WATER_SCHEDULE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): cv.string,
        **_WEEKLY_SCHEDULE_FIELDS,
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


def _build_weekly_schedule_days(
    service_call: ServiceCall,
) -> dict[str, DaySchedule | None]:
    """Build day-name -> schedule values from the service call data.

    Days omitted from the service call map to None, which tells python-bsblan not to
    modify that day.
    """
    return {
        day_name: _convert_time_slots_to_day_schedule(service_call.data.get(attr_name))
        for day_name, attr_name in _DAY_NAME_SLOT_ATTR_PAIRS
    }


def _resolve_config_entry(
    service_call: ServiceCall,
) -> tuple[BSBLanConfigEntry, dr.DeviceEntry]:
    """Resolve device_id from a service call into a loaded BSBLAN config entry."""
    device_id: str = service_call.data[ATTR_DEVICE_ID]

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

    return entry, device_entry


async def set_hot_water_schedule(service_call: ServiceCall) -> None:
    """Set hot water heating schedule."""
    entry, _ = _resolve_config_entry(service_call)
    client = entry.runtime_data.client

    days = _build_weekly_schedule_days(service_call)
    dhw_schedule = DHWSchedule(**days)

    LOGGER.debug("Setting hot water schedule: %s", dhw_schedule)

    try:
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
    entry, device_entry = _resolve_config_entry(service_call)
    client = entry.runtime_data.client
    await async_sync_device_time(
        client, device_entry.name or service_call.data[ATTR_DEVICE_ID]
    )


SYNC_TIME_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): cv.string,
    }
)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the BSB-LAN services."""
    hass.services.async_register(
        DOMAIN,
        "set_hot_water_schedule",
        set_hot_water_schedule,
        schema=SERVICE_SET_HOT_WATER_SCHEDULE_SCHEMA,
    )

    hass.services.async_register(
        DOMAIN,
        "sync_time",
        async_sync_time,
        schema=SYNC_TIME_SCHEMA,
    )
