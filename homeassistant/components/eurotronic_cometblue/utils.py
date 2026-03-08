"""Comet Blue Bluetooth utils."""

from __future__ import annotations

from datetime import time

import voluptuous as vol

from homeassistant.const import CONF_ENTITY_ID
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_registry import EntityRegistry

from .climate import MAX_TEMP, MIN_TEMP
from .const import (
    CONF_ALL_DAYS,
    CONF_DATETIME,
    CONF_DELETE,
    CONF_END,
    CONF_START,
    CONF_TEMPERATURE,
    DOMAIN,
)
from .coordinator import CometBlueDataUpdateCoordinator


def validate_half_precision(value: float) -> float:
    """Return True if the value is a half precision float."""

    try:
        r = value % 0.5
        if r != 0:
            raise vol.Invalid(
                f"value {value} is not a half precision float, remainder is {r}"
            )
    except TypeError as err:
        raise vol.Invalid(f"value {value} is not a float") from err
    return value


def validate_cometblue_schedule(schedule: dict[str, time]) -> dict[str, time] | None:
    """Validate the schedule of time ranges.

    Ensure they have no overlap and the end time is greater than the start time.
    """
    # If delete is set, return empty schedule
    if schedule.pop(CONF_DELETE, False):
        return {}

    # Emtpty schedule is valid, but should not do anything
    if not schedule:
        return None

    previous_to = None
    for i in range(1, 5):
        curr_start = f"{CONF_START}{i}"
        curr_end = f"{CONF_END}{i}"

        curr_keys = {curr_start, curr_end}.intersection(schedule)

        # No keys is valid (i.e. empty schedule)
        if len(curr_keys) == 0:
            continue

        # Check that both start and end entries are present
        if len(curr_keys) != 2:
            raise vol.Invalid(
                f"Missing start/end entry, only received {', '.join(repr(c) for c in curr_keys)}"
            )

        # Check if the start time of the current event is before the end time of the current event
        if schedule[curr_start] >= schedule[curr_end]:
            raise vol.Invalid(
                f"Invalid time range {i}, {schedule[curr_start]} is after"
                f" {schedule[curr_end]}"
            )

        # Check if the from time of the event is after the to time of the previous event
        if previous_to is not None and previous_to > schedule[curr_start]:
            raise vol.Invalid(
                f"Overlapping times found in schedule, '{curr_start}' is before '{CONF_END}{i - 1}'"
            )

        previous_to = schedule[curr_end]

    return schedule


def valid_cometblue_schedule_keys() -> list[str]:
    """Return a list of valid schedule keys."""
    return [f"{CONF_START}{i}" for i in range(1, 5)] + [
        f"{CONF_END}{i}" for i in range(1, 5)
    ]


SERVICE_ENTITY_SCHEMA = {vol.Required(CONF_ENTITY_ID): cv.entity_id}
SERVICE_DATETIME_SCHEMA = {
    vol.Optional(CONF_DATETIME): cv.datetime,
}

SCHEDULE_DAY_SCHEMA = vol.All(
    {
        vol.Optional(CONF_DELETE): cv.boolean,
        **{vol.Optional(item): cv.time for item in valid_cometblue_schedule_keys()},
    },
    validate_cometblue_schedule,
)
SERVICE_SCHEDULE_SCHEMA = {
    vol.Optional(day): SCHEDULE_DAY_SCHEMA for day in CONF_ALL_DAYS
}
SERVICE_HOLIDAY_SCHEMA = {
    vol.Required(CONF_START): cv.datetime,
    vol.Required(CONF_END): cv.datetime,
    vol.Required(CONF_TEMPERATURE): vol.All(
        vol.Coerce(float),
        vol.Range(min=MIN_TEMP, max=MAX_TEMP),
        validate_half_precision,
    ),
}


async def get_coordinator_for_service(
    hass: HomeAssistant, entity_id: str
) -> CometBlueDataUpdateCoordinator:
    """Return the coordinator for a given entity_id."""
    er = EntityRegistry(hass)
    await er.async_load()
    entity = er.async_get(entity_id)
    if not entity:
        raise ValueError(f"Entity '{entity_id}' not found")
    return hass.data[DOMAIN][entity.config_entry_id]
