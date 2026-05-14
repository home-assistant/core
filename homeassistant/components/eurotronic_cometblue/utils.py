"""Comet Blue Bluetooth utils."""

from datetime import time

from homeassistant.exceptions import ServiceValidationError

from .const import CONF_DELETE, CONF_END, CONF_START


def validate_half_precision(value: float) -> float:
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
            raise ServiceValidationError(
                f"Missing start/end entry, only received {', '.join(repr(c) for c in curr_keys)}"
            )

        # Check if the start time of the current event is before the end time of the current event
        if schedule[curr_start] >= schedule[curr_end]:
            raise ServiceValidationError(
                f"Invalid time range {i}, {schedule[curr_start]} is after"
                f" {schedule[curr_end]}"
            )

        # Check if the from time of the event is after the to time of the previous event
        if previous_to is not None and previous_to > schedule[curr_start]:
            raise ServiceValidationError(
                f"Overlapping times found in schedule, '{curr_start}' is before '{CONF_END}{i - 1}'"
            )

        previous_to = schedule[curr_end]

    return schedule


def valid_cometblue_schedule_keys() -> list[str]:
    """Return a list of valid schedule keys."""
    return [f"{CONF_START}{i}" for i in range(1, 5)] + [
        f"{CONF_END}{i}" for i in range(1, 5)
    ]
