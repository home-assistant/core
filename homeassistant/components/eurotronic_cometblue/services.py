"""Comet Blue services."""

from datetime import time, timedelta
from enum import StrEnum
import logging
from typing import Final, TypedDict, cast

import probatio

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
from homeassistant.util import dt as dt_util
from homeassistant.util.json import JsonArrayType, JsonObjectType

from .climate import MAX_TEMP, MIN_TEMP
from .const import DOMAIN
from .entity import CometBlueBluetoothEntity

LOGGER = logging.getLogger(__name__)


ATTR_MONDAY: Final = "monday"
ATTR_TUESDAY: Final = "tuesday"
ATTR_WEDNESDAY: Final = "wednesday"
ATTR_THURSDAY: Final = "thursday"
ATTR_FRIDAY: Final = "friday"
ATTR_SATURDAY: Final = "saturday"
ATTR_SUNDAY: Final = "sunday"
ATTR_START: Final = "start"
ATTR_END: Final = "end"
ATTR_FROM: Final = "from"
ATTR_TO: Final = "to"

ATTR_ALL_DAYS: Final = [
    ATTR_MONDAY,
    ATTR_TUESDAY,
    ATTR_WEDNESDAY,
    ATTR_THURSDAY,
    ATTR_FRIDAY,
    ATTR_SATURDAY,
    ATTR_SUNDAY,
]


class CometBlueService(StrEnum):
    """Store keys for Eurotronic Comet Blue services."""

    GET_SCHEDULE = "get_schedule"
    SET_SCHEDULE = "set_schedule"
    SET_HOLIDAY = "set_holiday"


class CometBlueServiceArgument(StrEnum):
    """Store keys for Eurotronic Comet Blue service arguments."""

    MONDAY = "monday"
    TUESDAY = "tuesday"
    WEDNESDAY = "wednesday"
    THURSDAY = "thursday"
    FRIDAY = "friday"
    SATURDAY = "saturday"
    SUNDAY = "sunday"
    FROM = "from"
    TO = "to"
    TEMPERATURE = "temperature"


_SCHEDULE_DAYS: Final = (
    CometBlueServiceArgument.MONDAY,
    CometBlueServiceArgument.TUESDAY,
    CometBlueServiceArgument.WEDNESDAY,
    CometBlueServiceArgument.THURSDAY,
    CometBlueServiceArgument.FRIDAY,
    CometBlueServiceArgument.SATURDAY,
    CometBlueServiceArgument.SUNDAY,
)

ScheduleEntry = TypedDict(
    "ScheduleEntry",
    {
        "from": time,
        "to": time,
    },
    total=False,
)


def _validate_half_precision(value: float) -> float:
    """Return True if the value is a half precision float."""

    r = value % 0.5
    if r != 0:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="invalid_half_precision",
            translation_placeholders={"value": str(value), "remainder": str(r)},
        )
    return value


def _validate_cometblue_schedule(
    schedule: list[ScheduleEntry],
) -> dict[str, time] | None:
    """Validate day schedule time ranges.

    Ensure they have no overlap and the end time is greater than the start time.
    """
    if not schedule:
        return {}

    schedule = sorted(
        schedule,
        key=lambda entry: entry.get(ATTR_FROM, time.min),
    )

    normalized_schedule: dict[str, time] = {}
    previous_to: time | None = None
    for i, entry in enumerate(schedule, start=1):
        start = entry.get(ATTR_FROM)
        end = entry.get(ATTR_TO)

        if start is None or end is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="missing_schedule_times",
            )

        # Check if the start time of the current event is before the end time of the current event
        if start >= end:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_schedule_time_range",
                translation_placeholders={
                    "index": str(i),
                    "start": str(start),
                    "end": str(end),
                },
            )

        # Check if the from time of the event is after the to time of the previous event
        if previous_to is not None and previous_to > start:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="overlapping_schedule_times",
                translation_placeholders={
                    "start": str(start),
                    "previous_end": str(previous_to),
                },
            )

        normalized_schedule[f"{ATTR_START}{i}"] = start
        normalized_schedule[f"{ATTR_END}{i}"] = end
        previous_to = end

    return normalized_schedule


SCHEDULE_ENTRY_SCHEMA = probatio.Schema(
    {
        probatio.Optional(ATTR_FROM): cv.time,
        probatio.Optional(ATTR_TO): cv.time,
    },
    extra=probatio.REMOVE_EXTRA,
)
SCHEDULE_DAY_SCHEMA = probatio.All(
    [SCHEDULE_ENTRY_SCHEMA],
    probatio.Length(max=4),
    _validate_cometblue_schedule,
)
SERVICE_SCHEDULE_SCHEMA = {
    probatio.Optional(day): SCHEDULE_DAY_SCHEMA for day in _SCHEDULE_DAYS
}
SERVICE_HOLIDAY_SCHEMA = {
    probatio.Required(CometBlueServiceArgument.FROM): cv.datetime,
    probatio.Required(CometBlueServiceArgument.TO): cv.datetime,
    probatio.Required(CometBlueServiceArgument.TEMPERATURE): probatio.All(
        probatio.Coerce(float),
        probatio.Range(min=MIN_TEMP, max=MAX_TEMP),
        _validate_half_precision,
    ),
}


async def get_schedule(
    entity: CometBlueBluetoothEntity, service_call: ServiceCall
) -> ServiceResponse:
    """Service call to retrieve the schedule from the device."""
    device_schedule = cast(
        dict[str, dict[str, str] | None],
        await entity.coordinator.send_command(
            entity.coordinator.device.get_multiple_async,
            {"values": ["weekdays"]},
        ),
    )

    week_schedule: JsonObjectType = {}
    for day in ATTR_ALL_DAYS:
        day_schedule = device_schedule.get(day, {})
        if day_schedule:
            curr_day_schedule: JsonArrayType = [
                {
                    ATTR_FROM: start,
                    ATTR_TO: end,
                }
                for i in range(1, 5)
                if (start := day_schedule.get(f"{ATTR_START}{i}")) is not None
                and (end := day_schedule.get(f"{ATTR_END}{i}")) is not None
            ]
            week_schedule[day] = curr_day_schedule

    return week_schedule


async def set_schedule(
    entity: CometBlueBluetoothEntity, service_call: ServiceCall
) -> None:
    """Service call to update the schedule on the device."""
    LOGGER.info(
        "Setting schedule for %s (%s) on days: %s",
        entity.entity_id,
        entity.coordinator.address,
        ", ".join(
            day for day in _SCHEDULE_DAYS if service_call.data.get(day) is not None
        ),
    )
    for day in _SCHEDULE_DAYS:
        LOGGER.debug(
            "Settings schedule for %s: %s",
            day,
            service_call.data.get(day),
        )
    values = {
        day: {k: v.strftime("%H:%M") for k, v in sched.items()}
        for day, sched in service_call.data.items()
        if sched is not None and day in _SCHEDULE_DAYS
    }
    await entity.coordinator.send_command(
        entity.coordinator.device.set_weekdays_async,
        {"values": values},
    )


async def set_holiday(
    entity: CometBlueBluetoothEntity, service_call: ServiceCall
) -> None:
    """Service call to update the holiday time on the device."""
    # ceil the start time to the next full hour
    away_start = service_call.data[CometBlueServiceArgument.FROM].replace(
        minute=0, second=0, microsecond=0
    ) + timedelta(hours=1)

    if away_start < dt_util.naive_now():
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="holiday_start_not_future",
        )

    LOGGER.info(
        "Setting holiday for %s (%s) until %s with temperature %s",
        entity.entity_id,
        entity.coordinator.address,
        service_call.data[CometBlueServiceArgument.TO],
        service_call.data[CometBlueServiceArgument.TEMPERATURE],
    )
    await entity.coordinator.send_command(
        entity.coordinator.device.set_holiday_async,
        {
            "number": 1,
            "values": {
                ATTR_START: service_call.data[CometBlueServiceArgument.FROM],
                ATTR_END: service_call.data[CometBlueServiceArgument.TO],
                ATTR_TEMPERATURE: service_call.data[
                    CometBlueServiceArgument.TEMPERATURE
                ],
            },
        },
    )


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the Eurotronic Comet Blue services."""

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        CometBlueService.GET_SCHEDULE,
        entity_domain=CLIMATE_DOMAIN,
        schema=None,
        supports_response=SupportsResponse.ONLY,
        func=get_schedule,
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        CometBlueService.SET_SCHEDULE,
        entity_domain=CLIMATE_DOMAIN,
        schema=cv.make_entity_service_schema(SERVICE_SCHEDULE_SCHEMA),
        supports_response=SupportsResponse.NONE,
        func=set_schedule,
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        CometBlueService.SET_HOLIDAY,
        entity_domain=CLIMATE_DOMAIN,
        schema=cv.make_entity_service_schema(SERVICE_HOLIDAY_SCHEMA),
        supports_response=SupportsResponse.NONE,
        func=set_holiday,
    )
