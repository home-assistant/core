"""Comet Blue services."""

from datetime import datetime, time
import logging
from typing import Final, TypedDict

import voluptuous as vol

from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.const import ATTR_TEMPERATURE
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv, service

from .climate import MAX_TEMP, MIN_TEMP
from .const import DOMAIN
from .entity import CometBlueBluetoothEntity

LOGGER = logging.getLogger(__name__)


ATTR_SCHEDULE: Final = "schedule"
ATTR_MONDAY: Final = "monday"
ATTR_TUESDAY: Final = "tuesday"
ATTR_WEDNESDAY: Final = "wednesday"
ATTR_THURSDAY: Final = "thursday"
ATTR_FRIDAY: Final = "friday"
ATTR_SATURDAY: Final = "saturday"
ATTR_SUNDAY: Final = "sunday"
ATTR_DELETE: Final = "delete"
ATTR_START: Final = "start"
ATTR_END: Final = "end"

ATTR_ALL_DAYS: Final = {
    ATTR_MONDAY,
    ATTR_TUESDAY,
    ATTR_WEDNESDAY,
    ATTR_THURSDAY,
    ATTR_FRIDAY,
    ATTR_SATURDAY,
    ATTR_SUNDAY,
}


class ScheduleEntry(TypedDict, total=False):
    """A single schedule entry passed to the service."""

    start: time
    end: time


class DaySchedule(TypedDict, total=False):
    """A single day's schedule payload."""

    schedule: list[ScheduleEntry]
    delete: bool


def _validate_half_precision(value: float) -> float:
    """Return True if the value is a half precision float."""

    try:
        r = value % 0.5
        if r != 0:
            raise ServiceValidationError(
                f"value {value} is not a half precision float, remainder is {r}"
            )
    except TypeError as err:
        raise ServiceValidationError(f"value {value} is not a float") from err
    return value


def _validate_cometblue_schedule(
    day_schedule: DaySchedule,
) -> dict[str, time] | None:
    """Validate day schedule time ranges.

    Ensure they have no overlap and the end time is greater than the start time.
    """
    if day_schedule.get(ATTR_DELETE):
        return {}

    schedule = day_schedule.get(ATTR_SCHEDULE, [])

    if not schedule:
        return None

    if len(schedule) > 4:
        raise ServiceValidationError("A maximum of 4 schedule entries is supported")

    schedule = sorted(
        schedule,
        key=lambda entry: entry.get(ATTR_START, time.min),
    )

    normalized_schedule: dict[str, time] = {}
    previous_to: time | None = None
    for i, entry in enumerate(schedule, start=1):
        if ATTR_START not in entry or ATTR_END not in entry:
            curr_keys = {ATTR_START, ATTR_END}.intersection(entry)
            raise ServiceValidationError(
                f"Missing start/end entry, only received {', '.join(repr(c) for c in curr_keys)}"
            )

        start = entry[ATTR_START]
        end = entry[ATTR_END]

        # Check if the start time of the current event is before the end time of the current event
        if start >= end:
            raise ServiceValidationError(
                f"Invalid time range {i}, {start} is after {end}"
            )

        # Check if the from time of the event is after the to time of the previous event
        if previous_to is not None and previous_to > start:
            raise ServiceValidationError(
                f"Overlapping times found in schedule, {start} is earlier than previous entry {previous_to} ends"
            )

        normalized_schedule[f"{ATTR_START}{i}"] = start
        normalized_schedule[f"{ATTR_END}{i}"] = end
        previous_to = end

    return normalized_schedule


SCHEDULE_ENTRY_SCHEMA = {
    vol.Optional(ATTR_START): cv.time,
    vol.Optional(ATTR_END): cv.time,
}
SCHEDULE_DAY_SCHEMA = vol.All(
    {
        vol.Optional(ATTR_SCHEDULE): [SCHEDULE_ENTRY_SCHEMA],
        vol.Optional(ATTR_DELETE): cv.boolean,
    },
    _validate_cometblue_schedule,
)
SERVICE_SCHEDULE_SCHEMA = {
    vol.Optional(day): SCHEDULE_DAY_SCHEMA for day in ATTR_ALL_DAYS
}
SERVICE_HOLIDAY_SCHEMA = {
    vol.Required(ATTR_START): cv.datetime,
    vol.Required(ATTR_END): cv.datetime,
    vol.Required(ATTR_TEMPERATURE): vol.All(
        vol.Coerce(float),
        vol.Range(min=MIN_TEMP, max=MAX_TEMP),
        _validate_half_precision,
    ),
}


async def get_schedule(
    entity: CometBlueBluetoothEntity, service_call: ServiceCall
) -> ServiceResponse:
    """Service call to retrieve the schedule from the device."""
    return await entity.coordinator.send_command(
        entity.coordinator.device.get_multiple_async,
        {"values": ["weekdays"]},
    )


async def set_schedule(
    entity: CometBlueBluetoothEntity, service_call: ServiceCall
) -> None:
    """Service call to update the schedule on the device."""
    LOGGER.info(
        "Setting schedule for %s (%s) on days: %s",
        entity.entity_id,
        entity.coordinator.device.device.address,
        ", ".join(
            day for day in ATTR_ALL_DAYS if service_call.data.get(day) is not None
        ),
    )
    for day in ATTR_ALL_DAYS:
        LOGGER.debug(
            "Settings schedule for %s: %s",
            day,
            service_call.data.get(day),
        )
    values = {
        day: {k: v.strftime("%H:%M") for k, v in sched.items()}
        for day, sched in service_call.data.items()
        if sched is not None and day in ATTR_ALL_DAYS
    }
    await entity.coordinator.send_command(
        entity.coordinator.device.set_weekdays_async,
        {"values": values},
    )


async def set_holiday(
    entity: CometBlueBluetoothEntity, service_call: ServiceCall
) -> None:
    """Service call to update the holiday time on the device."""
    if (
        datetime(
            service_call.data["start"].year,
            service_call.data["start"].month,
            service_call.data["start"].day,
            service_call.data["start"].hour,
        )
        < datetime.now()
    ):
        raise ServiceValidationError(
            "Start date (truncated to hour) must be in the future"
        )

    LOGGER.info(
        "Setting holiday for %s (%s) until %s with temperature %s",
        entity.entity_id,
        entity.coordinator.device.device.address,
        service_call.data["end"],
        service_call.data["temperature"],
    )
    await entity.coordinator.send_command(
        entity.coordinator.device.set_holiday_async,
        {
            "number": 1,
            "values": {
                "start": service_call.data["start"],
                "end": service_call.data["end"],
                "temperature": service_call.data["temperature"],
            },
        },
    )


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the Eurotronic Comet Blue services."""

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        "get_schedule",
        entity_domain=CLIMATE_DOMAIN,
        schema=None,
        supports_response=SupportsResponse.ONLY,
        func=get_schedule,
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        "set_schedule",
        entity_domain=CLIMATE_DOMAIN,
        schema=cv.make_entity_service_schema(SERVICE_SCHEDULE_SCHEMA),
        supports_response=SupportsResponse.NONE,
        func=set_schedule,
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        "set_holiday",
        entity_domain=CLIMATE_DOMAIN,
        schema=cv.make_entity_service_schema(SERVICE_HOLIDAY_SCHEMA),
        supports_response=SupportsResponse.NONE,
        func=set_holiday,
    )
