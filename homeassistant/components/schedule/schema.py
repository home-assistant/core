"""Schemas for the schedule integration."""

from datetime import time
from typing import Any

import probatio

from homeassistant.const import CONF_ICON, CONF_ID, CONF_NAME
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import VolDictType

from .const import CONF_ALL_DAYS, CONF_DATA, CONF_FROM, CONF_TO


def valid_schedule(schedule: list[dict[str, str]]) -> list[dict[str, str]]:
    """Validate the schedule of time ranges.

    Ensure they have no overlap and the end time is greater than the start time.
    """
    # Empty schedule is valid
    if not schedule:
        return schedule

    # Sort the schedule by start times
    schedule = sorted(schedule, key=lambda time_range: time_range[CONF_FROM])

    # Check if the start time of the next event is before
    # the end time of the previous event
    previous_to = None
    for time_range in schedule:
        if time_range[CONF_FROM] >= time_range[CONF_TO]:
            raise probatio.Invalid(
                f"Invalid time range, from {time_range[CONF_FROM]} is after"
                f" {time_range[CONF_TO]}"
            )

        # Check if the from time of the event is after the to time of the previous event
        if previous_to is not None and previous_to > time_range[CONF_FROM]:
            raise probatio.Invalid("Overlapping times found in schedule")

        previous_to = time_range[CONF_TO]

    return schedule


def deserialize_to_time(value: Any) -> Any:
    """Convert 24:00 and 24:00:00 to time.max."""
    if not isinstance(value, str):
        return cv.time(value)

    parts = value.split(":")
    if len(parts) < 2:
        return cv.time(value)
    hour = int(parts[0])
    minute = int(parts[1])

    if hour == 24 and minute == 0:
        return time.max

    return cv.time(value)


def serialize_to_time(value: Any) -> Any:
    """Convert time.max to 24:00:00."""
    if value == time.max:
        return "24:00:00"
    return probatio.Coerce(str)(value)


BASE_SCHEMA: VolDictType = {
    probatio.Required(CONF_NAME): probatio.All(str, probatio.NonEmpty()),
    probatio.Optional(CONF_ICON): cv.icon,
}

# Extra data that the user can set on each time range
CUSTOM_DATA_SCHEMA = probatio.Schema({str: probatio.Any(bool, str, int, float)})

TIME_RANGE_SCHEMA: VolDictType = {
    probatio.Required(CONF_FROM): cv.time,
    probatio.Required(CONF_TO): deserialize_to_time,
    probatio.Optional(CONF_DATA): CUSTOM_DATA_SCHEMA,
}

# Serialize time in validated config
STORAGE_TIME_RANGE_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_FROM): probatio.Coerce(str),
        probatio.Required(CONF_TO): serialize_to_time,
        probatio.Optional(CONF_DATA): CUSTOM_DATA_SCHEMA,
    }
)

SCHEDULE_SCHEMA: VolDictType = {
    probatio.Optional(day, default=[]): probatio.All(
        probatio.EnsureList(), [TIME_RANGE_SCHEMA], valid_schedule
    )
    for day in CONF_ALL_DAYS
}
STORAGE_SCHEDULE_SCHEMA: VolDictType = {
    probatio.Optional(day, default=[]): probatio.All(
        probatio.EnsureList(),
        [TIME_RANGE_SCHEMA],
        valid_schedule,
        [STORAGE_TIME_RANGE_SCHEMA],
    )
    for day in CONF_ALL_DAYS
}

# Validate storage config
STORAGE_SCHEMA = probatio.Schema(
    {probatio.Required(CONF_ID): cv.string} | BASE_SCHEMA | STORAGE_SCHEDULE_SCHEMA
)
# Validate + transform entity config
ENTITY_SCHEMA = probatio.Schema(
    {probatio.Required(CONF_ID): cv.string} | BASE_SCHEMA | SCHEDULE_SCHEMA
)
