"""Timer implementation for intents using timer_list."""

from datetime import timedelta
from enum import StrEnum
import logging
from typing import Any, override

import voluptuous as vol

from homeassistant.components.timer_list import (
    TimerItem,
    TimerListEntity,
    TimerStatus,
    async_get_timer_list_entity,
)
from homeassistant.const import ATTR_DEVICE_ID, ATTR_ID, ATTR_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, intent
from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)

TIMER_NOT_FOUND_RESPONSE = "timer_not_found"
MULTIPLE_TIMERS_MATCHED_RESPONSE = "multiple_timers_matched"
NO_TIMER_SUPPORT_RESPONSE = "no_timer_support"


class TimerNotFoundError(intent.IntentHandleError):
    """Error when a timer could not be found by name or start time."""

    def __init__(self) -> None:
        """Initialize error."""
        super().__init__("Timer not found", TIMER_NOT_FOUND_RESPONSE)


class MultipleTimersMatchedError(intent.IntentHandleError):
    """Error when multiple timers matched name or start time."""

    def __init__(self) -> None:
        """Initialize error."""
        super().__init__("Multiple timers matched", MULTIPLE_TIMERS_MATCHED_RESPONSE)


class TimersNotSupportedError(intent.IntentHandleError):
    """Error when a timer intent is used from a device without a timer list.

    The device has no ``timer_list`` entity, so it cannot manage timers.
    """

    def __init__(self, device_id: str | None = None) -> None:
        """Initialize error."""
        super().__init__(
            f"Device does not support timers: device_id={device_id}",
            NO_TIMER_SUPPORT_RESPONSE,
        )


@callback
def async_device_supports_timers(hass: HomeAssistant, device_id: str) -> bool:
    """Return True if a device has a timer_list entity to manage timers."""
    return async_get_timer_list_entity(hass, device_id) is not None


# -----------------------------------------------------------------------------


@callback
def _get_timer_entity(hass: HomeAssistant, device_id: str | None) -> TimerListEntity:
    """Return the requesting device's timer_list entity or raise if it has none."""
    if (
        device_id is None
        or (entity := async_get_timer_list_entity(hass, device_id)) is None
    ):
        raise TimersNotSupportedError(device_id)
    return entity


def _normalize_start_time(
    hours: int | None, minutes: int | None, seconds: int | None
) -> tuple[int, int, int]:
    """Normalize an hours/minutes/seconds breakdown to a canonical form.

    Used to compare a timer's original duration against a voice command's
    start-time slots regardless of which of hours/minutes/seconds were
    explicitly given (e.g. "the 5 minute timer" and "the 0 hour 5 minute 0
    second timer" both normalize to the same (0, 5, 0)).
    """
    total_seconds = (60 * 60 * (hours or 0)) + (60 * (minutes or 0)) + (seconds or 0)
    total_minutes, norm_seconds = divmod(total_seconds, 60)
    norm_hours, norm_minutes = divmod(total_minutes, 60)
    return norm_hours, norm_minutes, norm_seconds


@callback
def _item_start_time(item: TimerItem) -> tuple[int, int, int]:
    """Return a timer's original duration as normalized (hours, minutes, seconds)."""
    return _normalize_start_time(None, None, int(item.duration.total_seconds()))


class FindTimerFilter(StrEnum):
    """Type of filter to apply when finding a timer."""

    ONLY_ACTIVE = "only_active"
    ONLY_INACTIVE = "only_inactive"


def _find_timer(
    entity: TimerListEntity,
    slots: dict[str, Any],
    find_filter: FindTimerFilter | None = None,
) -> TimerItem:
    """Match a single timer on the requesting device or raise an error."""
    matching_timers = [
        item
        for item in entity.timers
        if item.status in (TimerStatus.ACTIVE, TimerStatus.PAUSED)
    ]
    has_filter = False

    if find_filter:
        # Filter by active state
        has_filter = True
        if find_filter == FindTimerFilter.ONLY_ACTIVE:
            matching_timers = [
                t for t in matching_timers if t.status == TimerStatus.ACTIVE
            ]
        elif find_filter == FindTimerFilter.ONLY_INACTIVE:
            matching_timers = [
                t for t in matching_timers if t.status != TimerStatus.ACTIVE
            ]

        if len(matching_timers) == 1:
            # Only 1 match
            return matching_timers[0]

    # Search by name first
    name: str | None = None
    if "name" in slots:
        has_filter = True
        name = slots["name"]["value"]
        assert name is not None
        name_norm = _normalize_name(name)

        matching_timers = [
            t for t in matching_timers if _normalize_name(t.name or "") == name_norm
        ]
        if len(matching_timers) == 1:
            # Only 1 match
            return matching_timers[0]

    # Use starting time to disambiguate
    start_hours: int | None = None
    if "start_hours" in slots:
        start_hours = int(slots["start_hours"]["value"])

    start_minutes: int | None = None
    if "start_minutes" in slots:
        start_minutes = int(slots["start_minutes"]["value"])

    start_seconds: int | None = None
    if "start_seconds" in slots:
        start_seconds = int(slots["start_seconds"]["value"])

    if (
        (start_hours is not None)
        or (start_minutes is not None)
        or (start_seconds is not None)
    ):
        has_filter = True
        norm_start = _normalize_start_time(start_hours, start_minutes, start_seconds)
        matching_timers = [
            t for t in matching_timers if _item_start_time(t) == norm_start
        ]

        if len(matching_timers) == 1:
            # Only 1 match remaining
            return matching_timers[0]

    if (not has_filter) and (len(matching_timers) == 1):
        # Only 1 match remaining with no filter
        return matching_timers[0]

    if matching_timers:
        raise MultipleTimersMatchedError

    _LOGGER.warning(
        "Timer not found: name=%s, hours=%s, minutes=%s, seconds=%s",
        name,
        start_hours,
        start_minutes,
        start_seconds,
    )

    raise TimerNotFoundError


def _find_timers(entity: TimerListEntity, slots: dict[str, Any]) -> list[TimerItem]:
    """Match the requesting device's timers with constraints."""
    matching_timers = [
        item
        for item in entity.timers
        if item.status in (TimerStatus.ACTIVE, TimerStatus.PAUSED)
    ]

    # Filter by name first
    if "name" in slots:
        name = slots["name"]["value"]
        assert name is not None
        name_norm = _normalize_name(name)

        matching_timers = [
            t for t in matching_timers if _normalize_name(t.name or "") == name_norm
        ]
        if not matching_timers:
            # No matches
            return matching_timers

    # Use starting time to filter, if present
    start_hours: int | None = None
    if "start_hours" in slots:
        start_hours = int(slots["start_hours"]["value"])

    start_minutes: int | None = None
    if "start_minutes" in slots:
        start_minutes = int(slots["start_minutes"]["value"])

    start_seconds: int | None = None
    if "start_seconds" in slots:
        start_seconds = int(slots["start_seconds"]["value"])

    if (
        (start_hours is not None)
        or (start_minutes is not None)
        or (start_seconds is not None)
    ):
        norm_start = _normalize_start_time(start_hours, start_minutes, start_seconds)
        matching_timers = [
            t for t in matching_timers if _item_start_time(t) == norm_start
        ]

    return matching_timers


def _normalize_name(name: str) -> str:
    """Normalize name for comparison."""
    return name.strip().casefold()


def _get_total_seconds(slots: dict[str, Any]) -> int:
    """Return the total number of seconds from hours/minutes/seconds slots."""
    total_seconds = 0
    if "hours" in slots:
        total_seconds += 60 * 60 * int(slots["hours"]["value"])

    if "minutes" in slots:
        total_seconds += 60 * int(slots["minutes"]["value"])

    if "seconds" in slots:
        total_seconds += int(slots["seconds"]["value"])

    return total_seconds


def _round_time(hours: int, minutes: int, seconds: int) -> tuple[int, int, int]:
    """Round time to a lower precision for feedback."""
    if hours > 0:
        # No seconds, round up above 45 minutes and down below 15
        rounded_hours = hours
        rounded_seconds = 0
        if minutes > 45:
            # 01:50:30 -> 02:00:00
            rounded_hours += 1
            rounded_minutes = 0
        elif minutes < 15:
            # 01:10:30 -> 01:00:00
            rounded_minutes = 0
        else:
            # 01:25:30 -> 01:30:00
            rounded_minutes = 30
    elif minutes > 0:
        # Round up above 45 seconds, down below 15
        rounded_hours = 0
        rounded_minutes = minutes
        if seconds > 45:
            # 00:01:50 -> 00:02:00
            rounded_minutes += 1
            rounded_seconds = 0
        elif seconds < 15:
            # 00:01:10 -> 00:01:00
            rounded_seconds = 0
        else:
            # 00:01:25 -> 00:01:30
            rounded_seconds = 30
    else:
        # Round up above 50 seconds, exact below 10, and down to nearest 10
        # otherwise.
        rounded_hours = 0
        rounded_minutes = 0
        if seconds > 50:
            # 00:00:55 -> 00:01:00
            rounded_minutes = 1
            rounded_seconds = 0
        elif seconds < 10:
            # 00:00:09 -> 00:00:09
            rounded_seconds = seconds
        else:
            # 00:01:25 -> 00:01:20
            rounded_seconds = seconds - (seconds % 10)

    return rounded_hours, rounded_minutes, rounded_seconds


class StartTimerIntentHandler(intent.IntentHandler):
    """Intent handler for starting a new timer."""

    intent_type = intent.INTENT_START_TIMER
    description = "Starts a new timer"
    slot_schema = {
        vol.Required(vol.Any("hours", "minutes", "seconds")): cv.positive_int,
        vol.Optional("name"): cv.string,
    }

    @override
    async def async_handle(self, intent_obj: intent.Intent) -> intent.IntentResponse:
        """Handle the intent."""
        hass = intent_obj.hass
        entity = _get_timer_entity(hass, intent_obj.device_id)
        slots = self.async_validate_slots(intent_obj.slots)

        name: str | None = None
        if "name" in slots:
            name = slots["name"]["value"]

        total_seconds = _get_total_seconds(slots)
        timer_id = await entity.async_start_timer(
            name=name, duration=timedelta(seconds=total_seconds)
        )

        _LOGGER.debug(
            "Timer started: id=%s, name=%s, seconds=%s, device_id=%s",
            timer_id,
            name,
            total_seconds,
            intent_obj.device_id,
        )

        return intent_obj.create_response()


class CancelTimerIntentHandler(intent.IntentHandler):
    """Intent handler for cancelling a timer."""

    intent_type = intent.INTENT_CANCEL_TIMER
    description = "Cancels a timer"
    slot_schema = {
        vol.Any("start_hours", "start_minutes", "start_seconds"): cv.positive_int,
        vol.Optional("name"): cv.string,
    }

    @override
    async def async_handle(self, intent_obj: intent.Intent) -> intent.IntentResponse:
        """Handle the intent."""
        hass = intent_obj.hass
        entity = _get_timer_entity(hass, intent_obj.device_id)
        slots = self.async_validate_slots(intent_obj.slots)

        timer = _find_timer(entity, slots)
        await entity.async_cancel_timer(timer.timer_id)
        return intent_obj.create_response()


class CancelAllTimersIntentHandler(intent.IntentHandler):
    """Intent handler for cancelling all timers."""

    intent_type = intent.INTENT_CANCEL_ALL_TIMERS
    description = "Cancels all timers"

    @override
    async def async_handle(self, intent_obj: intent.Intent) -> intent.IntentResponse:
        """Handle the intent."""
        hass = intent_obj.hass
        entity = _get_timer_entity(hass, intent_obj.device_id)
        slots = self.async_validate_slots(intent_obj.slots)
        canceled = 0

        for timer in _find_timers(entity, slots):
            await entity.async_cancel_timer(timer.timer_id)
            canceled += 1

        response = intent_obj.create_response()
        response.async_set_speech_slots({"canceled": canceled})

        return response


class IncreaseTimerIntentHandler(intent.IntentHandler):
    """Intent handler for increasing the time of a timer."""

    intent_type = intent.INTENT_INCREASE_TIMER
    description = "Adds more time to a timer"
    slot_schema = {
        vol.Any("hours", "minutes", "seconds"): cv.positive_int,
        vol.Any("start_hours", "start_minutes", "start_seconds"): cv.positive_int,
        vol.Optional("name"): cv.string,
    }

    @override
    async def async_handle(self, intent_obj: intent.Intent) -> intent.IntentResponse:
        """Handle the intent."""
        hass = intent_obj.hass
        entity = _get_timer_entity(hass, intent_obj.device_id)
        slots = self.async_validate_slots(intent_obj.slots)

        total_seconds = _get_total_seconds(slots)
        timer = _find_timer(entity, slots)
        if total_seconds:
            await entity.async_add_time(
                timer.timer_id, timedelta(seconds=total_seconds)
            )
        return intent_obj.create_response()


class DecreaseTimerIntentHandler(intent.IntentHandler):
    """Intent handler for decreasing the time of a timer."""

    intent_type = intent.INTENT_DECREASE_TIMER
    description = "Removes time from a timer"
    slot_schema = {
        vol.Required(vol.Any("hours", "minutes", "seconds")): cv.positive_int,
        vol.Any("start_hours", "start_minutes", "start_seconds"): cv.positive_int,
        vol.Optional("name"): cv.string,
    }

    @override
    async def async_handle(self, intent_obj: intent.Intent) -> intent.IntentResponse:
        """Handle the intent."""
        hass = intent_obj.hass
        entity = _get_timer_entity(hass, intent_obj.device_id)
        slots = self.async_validate_slots(intent_obj.slots)

        total_seconds = _get_total_seconds(slots)
        timer = _find_timer(entity, slots)
        if total_seconds:
            await entity.async_add_time(
                timer.timer_id, timedelta(seconds=-total_seconds)
            )
        return intent_obj.create_response()


class PauseTimerIntentHandler(intent.IntentHandler):
    """Intent handler for pausing a running timer."""

    intent_type = intent.INTENT_PAUSE_TIMER
    description = "Pauses a running timer"
    slot_schema = {
        vol.Any("start_hours", "start_minutes", "start_seconds"): cv.positive_int,
        vol.Optional("name"): cv.string,
    }

    @override
    async def async_handle(self, intent_obj: intent.Intent) -> intent.IntentResponse:
        """Handle the intent."""
        hass = intent_obj.hass
        entity = _get_timer_entity(hass, intent_obj.device_id)
        slots = self.async_validate_slots(intent_obj.slots)

        timer = _find_timer(entity, slots, find_filter=FindTimerFilter.ONLY_ACTIVE)
        await entity.async_pause_timer(timer.timer_id)
        return intent_obj.create_response()


class UnpauseTimerIntentHandler(intent.IntentHandler):
    """Intent handler for unpausing a paused timer."""

    intent_type = intent.INTENT_UNPAUSE_TIMER
    description = "Resumes a paused timer"
    slot_schema = {
        vol.Any("start_hours", "start_minutes", "start_seconds"): cv.positive_int,
        vol.Optional("name"): cv.string,
    }

    @override
    async def async_handle(self, intent_obj: intent.Intent) -> intent.IntentResponse:
        """Handle the intent."""
        hass = intent_obj.hass
        entity = _get_timer_entity(hass, intent_obj.device_id)
        slots = self.async_validate_slots(intent_obj.slots)

        timer = _find_timer(entity, slots, find_filter=FindTimerFilter.ONLY_INACTIVE)
        await entity.async_unpause_timer(timer.timer_id)
        return intent_obj.create_response()


class TimerStatusIntentHandler(intent.IntentHandler):
    """Intent handler for reporting the status of a timer."""

    intent_type = intent.INTENT_TIMER_STATUS
    description = "Reports the current status of timers"
    slot_schema = {
        vol.Any("start_hours", "start_minutes", "start_seconds"): cv.positive_int,
        vol.Optional("name"): cv.string,
    }

    @override
    async def async_handle(self, intent_obj: intent.Intent) -> intent.IntentResponse:
        """Handle the intent."""
        hass = intent_obj.hass
        entity = _get_timer_entity(hass, intent_obj.device_id)
        slots = self.async_validate_slots(intent_obj.slots)

        now = dt_util.utcnow()
        statuses: list[dict[str, Any]] = []
        for timer in _find_timers(entity, slots):
            total_seconds = round(timer.remaining_at(now).total_seconds())

            minutes, seconds = divmod(total_seconds, 60)
            hours, minutes = divmod(minutes, 60)

            # Get lower-precision time for feedback
            rounded_hours, rounded_minutes, rounded_seconds = _round_time(
                hours, minutes, seconds
            )

            start_hours, start_minutes, start_seconds = _item_start_time(timer)
            statuses.append(
                {
                    ATTR_ID: timer.timer_id,
                    ATTR_NAME: timer.name or "",
                    ATTR_DEVICE_ID: intent_obj.device_id,
                    "language": hass.config.language,
                    "start_hours": start_hours,
                    "start_minutes": start_minutes,
                    "start_seconds": start_seconds,
                    "is_active": timer.status == TimerStatus.ACTIVE,
                    "hours_left": hours,
                    "minutes_left": minutes,
                    "seconds_left": seconds,
                    "rounded_hours_left": rounded_hours,
                    "rounded_minutes_left": rounded_minutes,
                    "rounded_seconds_left": rounded_seconds,
                    "total_seconds_left": total_seconds,
                }
            )

        response = intent_obj.create_response()
        response.async_set_speech_slots({"timers": statuses})

        return response
