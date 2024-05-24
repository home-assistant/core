"""Timer implementation for intents."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from functools import cached_property
import logging
import time
from typing import Any

import voluptuous as vol

from homeassistant.const import ATTR_DEVICE_ID, ATTR_ID, ATTR_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import (
    area_registry as ar,
    config_validation as cv,
    device_registry as dr,
    intent,
)
from homeassistant.util import ulid

from .const import TIMER_DATA

_LOGGER = logging.getLogger(__name__)

TIMER_NOT_FOUND_RESPONSE = "timer_not_found"
MULTIPLE_TIMERS_MATCHED_RESPONSE = "multiple_timers_matched"


@dataclass
class TimerInfo:
    """Information for a single timer."""

    id: str
    """Unique id of the timer."""

    name: str | None
    """User-provided name for timer."""

    seconds: int
    """Total number of seconds the timer should run for."""

    device_id: str | None
    """Id of the device where the timer was set."""

    start_hours: int | None
    """Number of hours the timer should run as given by the user."""

    start_minutes: int | None
    """Number of minutes the timer should run as given by the user."""

    start_seconds: int | None
    """Number of seconds the timer should run as given by the user."""

    created_at: int
    """Timestamp when timer was created (time.monotonic_ns)"""

    updated_at: int
    """Timestamp when timer was last updated (time.monotonic_ns)"""

    language: str
    """Language of command used to set the timer."""

    is_active: bool = True
    """True if timer is ticking down."""

    area_id: str | None = None
    """Id of area that the device belongs to."""

    area_name: str | None = None
    """Normalized name of the area that the device belongs to."""

    floor_id: str | None = None
    """Id of floor that the device's area belongs to."""

    @property
    def seconds_left(self) -> int:
        """Return number of seconds left on the timer."""
        if not self.is_active:
            return self.seconds

        now = time.monotonic_ns()
        seconds_running = int((now - self.updated_at) / 1e9)
        return max(0, self.seconds - seconds_running)

    @cached_property
    def name_normalized(self) -> str:
        """Return normalized timer name."""
        return _normalize_name(self.name or "")

    def cancel(self) -> None:
        """Cancel the timer."""
        self.seconds = 0
        self.updated_at = time.monotonic_ns()
        self.is_active = False

    def pause(self) -> None:
        """Pause the timer."""
        self.seconds = self.seconds_left
        self.updated_at = time.monotonic_ns()
        self.is_active = False

    def unpause(self) -> None:
        """Unpause the timer."""
        self.updated_at = time.monotonic_ns()
        self.is_active = True

    def add_time(self, seconds: int) -> None:
        """Add time to the timer.

        Seconds may be negative to remove time instead.
        """
        self.seconds = max(0, self.seconds_left + seconds)
        self.updated_at = time.monotonic_ns()

    def finish(self) -> None:
        """Finish the timer."""
        self.seconds = 0
        self.updated_at = time.monotonic_ns()
        self.is_active = False


class TimerEventType(StrEnum):
    """Event type in timer handler."""

    STARTED = "started"
    """Timer has started."""

    UPDATED = "updated"
    """Timer has been increased, decreased, paused, or unpaused."""

    CANCELLED = "cancelled"
    """Timer has been cancelled."""

    FINISHED = "finished"
    """Timer finished without being cancelled."""


type TimerHandler = Callable[[TimerEventType, TimerInfo], None]


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


class TimerManager:
    """Manager for intent timers."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize timer manager."""
        self.hass = hass

        # timer id -> timer
        self.timers: dict[str, TimerInfo] = {}
        self.timer_tasks: dict[str, asyncio.Task] = {}

        self.handlers: list[TimerHandler] = []

    def register_handler(self, handler: TimerHandler) -> Callable[[], None]:
        """Register a timer handler.

        Returns a callable to unregister.
        """
        self.handlers.append(handler)
        return lambda: self.handlers.remove(handler)

    def start_timer(
        self,
        hours: int | None,
        minutes: int | None,
        seconds: int | None,
        language: str,
        device_id: str | None,
        name: str | None = None,
    ) -> str:
        """Start a timer."""
        total_seconds = 0
        if hours is not None:
            total_seconds += 60 * 60 * hours

        if minutes is not None:
            total_seconds += 60 * minutes

        if seconds is not None:
            total_seconds += seconds

        timer_id = ulid.ulid_now()
        created_at = time.monotonic_ns()
        timer = TimerInfo(
            id=timer_id,
            name=name,
            start_hours=hours,
            start_minutes=minutes,
            start_seconds=seconds,
            seconds=total_seconds,
            language=language,
            device_id=device_id,
            created_at=created_at,
            updated_at=created_at,
        )

        # Fill in area/floor info
        device_registry = dr.async_get(self.hass)
        if device_id and (device := device_registry.async_get(device_id)):
            timer.area_id = device.area_id
            area_registry = ar.async_get(self.hass)
            if device.area_id and (
                area := area_registry.async_get_area(device.area_id)
            ):
                timer.area_name = _normalize_name(area.name)
                timer.floor_id = area.floor_id

        self.timers[timer_id] = timer
        self.timer_tasks[timer_id] = self.hass.async_create_background_task(
            self._wait_for_timer(timer_id, total_seconds, created_at),
            name=f"Timer {timer_id}",
        )

        for handler in self.handlers:
            handler(TimerEventType.STARTED, timer)

        _LOGGER.debug(
            "Timer started: id=%s, name=%s, hours=%s, minutes=%s, seconds=%s, device_id=%s",
            timer_id,
            name,
            hours,
            minutes,
            seconds,
            device_id,
        )

        return timer_id

    async def _wait_for_timer(
        self, timer_id: str, seconds: int, updated_at: int
    ) -> None:
        """Sleep until timer is up. Timer is only finished if it hasn't been updated."""
        try:
            await asyncio.sleep(seconds)
            if (timer := self.timers.get(timer_id)) and (
                timer.updated_at == updated_at
            ):
                self._timer_finished(timer_id)
        except asyncio.CancelledError:
            pass  # expected when timer is updated

    def cancel_timer(self, timer_id: str) -> None:
        """Cancel a timer."""
        timer = self.timers.pop(timer_id, None)
        if timer is None:
            raise TimerNotFoundError

        if timer.is_active:
            task = self.timer_tasks.pop(timer_id)
            task.cancel()

        timer.cancel()

        for handler in self.handlers:
            handler(TimerEventType.CANCELLED, timer)

        _LOGGER.debug(
            "Timer cancelled: id=%s, name=%s, seconds_left=%s, device_id=%s",
            timer_id,
            timer.name,
            timer.seconds_left,
            timer.device_id,
        )

    def add_time(self, timer_id: str, seconds: int) -> None:
        """Add time to a timer."""
        timer = self.timers.get(timer_id)
        if timer is None:
            raise TimerNotFoundError

        if seconds == 0:
            # Don't bother cancelling and recreating the timer task
            return

        timer.add_time(seconds)
        if timer.is_active:
            task = self.timer_tasks.pop(timer_id)
            task.cancel()
            self.timer_tasks[timer_id] = self.hass.async_create_background_task(
                self._wait_for_timer(timer_id, timer.seconds, timer.updated_at),
                name=f"Timer {timer_id}",
            )

        for handler in self.handlers:
            handler(TimerEventType.UPDATED, timer)

        if seconds > 0:
            log_verb = "increased"
            log_seconds = seconds
        else:
            log_verb = "decreased"
            log_seconds = -seconds

        _LOGGER.debug(
            "Timer %s by %s second(s): id=%s, name=%s, seconds_left=%s, device_id=%s",
            log_verb,
            log_seconds,
            timer_id,
            timer.name,
            timer.seconds_left,
            timer.device_id,
        )

    def remove_time(self, timer_id: str, seconds: int) -> None:
        """Remove time from a timer."""
        self.add_time(timer_id, -seconds)

    def pause_timer(self, timer_id: str) -> None:
        """Pauses a timer."""
        timer = self.timers.get(timer_id)
        if timer is None:
            raise TimerNotFoundError

        if not timer.is_active:
            # Already paused
            return

        timer.pause()
        task = self.timer_tasks.pop(timer_id)
        task.cancel()

        for handler in self.handlers:
            handler(TimerEventType.UPDATED, timer)

        _LOGGER.debug(
            "Timer paused: id=%s, name=%s, seconds_left=%s, device_id=%s",
            timer_id,
            timer.name,
            timer.seconds_left,
            timer.device_id,
        )

    def unpause_timer(self, timer_id: str) -> None:
        """Unpause a timer."""
        timer = self.timers.get(timer_id)
        if timer is None:
            raise TimerNotFoundError

        if timer.is_active:
            # Already unpaused
            return

        timer.unpause()
        self.timer_tasks[timer_id] = self.hass.async_create_background_task(
            self._wait_for_timer(timer_id, timer.seconds_left, timer.updated_at),
            name=f"Timer {timer.id}",
        )

        for handler in self.handlers:
            handler(TimerEventType.UPDATED, timer)

        _LOGGER.debug(
            "Timer unpaused: id=%s, name=%s, seconds_left=%s, device_id=%s",
            timer_id,
            timer.name,
            timer.seconds_left,
            timer.device_id,
        )

    def _timer_finished(self, timer_id: str) -> None:
        """Call event handlers when a timer finishes."""
        timer = self.timers.pop(timer_id)

        timer.finish()
        for handler in self.handlers:
            handler(TimerEventType.FINISHED, timer)

        _LOGGER.debug(
            "Timer finished: id=%s, name=%s, device_id=%s",
            timer_id,
            timer.name,
            timer.device_id,
        )


@callback
def async_register_timer_handler(
    hass: HomeAssistant, handler: TimerHandler
) -> Callable[[], None]:
    """Register a handler for timer events.

    Returns a callable to unregister.
    """
    timer_manager: TimerManager = hass.data[TIMER_DATA]
    return timer_manager.register_handler(handler)


# -----------------------------------------------------------------------------


def _find_timer(
    hass: HomeAssistant, slots: dict[str, Any], device_id: str | None
) -> TimerInfo:
    """Match a single timer with constraints or raise an error."""
    timer_manager: TimerManager = hass.data[TIMER_DATA]
    matching_timers: list[TimerInfo] = list(timer_manager.timers.values())
    has_filter = False

    # Search by name first
    name: str | None = None
    if "name" in slots:
        has_filter = True
        name = slots["name"]["value"]
        assert name is not None
        name_norm = _normalize_name(name)

        matching_timers = [t for t in matching_timers if t.name_normalized == name_norm]
        if len(matching_timers) == 1:
            # Only 1 match
            return matching_timers[0]

    # Search by area name
    area_name: str | None = None
    if "area" in slots:
        has_filter = True
        area_name = slots["area"]["value"]
        assert area_name is not None
        area_name_norm = _normalize_name(area_name)

        matching_timers = [t for t in matching_timers if t.area_name == area_name_norm]
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
        matching_timers = [
            t
            for t in matching_timers
            if (t.start_hours == start_hours)
            and (t.start_minutes == start_minutes)
            and (t.start_seconds == start_seconds)
        ]

        if len(matching_timers) == 1:
            # Only 1 match remaining
            return matching_timers[0]

    if (not has_filter) and (len(matching_timers) == 1):
        # Only 1 match remaining with no filter
        return matching_timers[0]

    # Use device id
    if matching_timers and device_id:
        matching_device_timers = [
            t for t in matching_timers if (t.device_id == device_id)
        ]
        if len(matching_device_timers) == 1:
            # Only 1 match remaining
            return matching_device_timers[0]

        # Try area/floor
        device_registry = dr.async_get(hass)
        area_registry = ar.async_get(hass)
        if (
            (device := device_registry.async_get(device_id))
            and device.area_id
            and (area := area_registry.async_get_area(device.area_id))
        ):
            # Try area
            matching_area_timers = [
                t for t in matching_timers if (t.area_id == area.id)
            ]
            if len(matching_area_timers) == 1:
                # Only 1 match remaining
                return matching_area_timers[0]

            # Try floor
            matching_floor_timers = [
                t for t in matching_timers if (t.floor_id == area.floor_id)
            ]
            if len(matching_floor_timers) == 1:
                # Only 1 match remaining
                return matching_floor_timers[0]

    if matching_timers:
        raise MultipleTimersMatchedError

    _LOGGER.warning(
        "Timer not found: name=%s, area=%s, hours=%s, minutes=%s, seconds=%s, device_id=%s",
        name,
        area_name,
        start_hours,
        start_minutes,
        start_seconds,
        device_id,
    )

    raise TimerNotFoundError


def _find_timers(
    hass: HomeAssistant, slots: dict[str, Any], device_id: str | None
) -> list[TimerInfo]:
    """Match multiple timers with constraints or raise an error."""
    timer_manager: TimerManager = hass.data[TIMER_DATA]
    matching_timers: list[TimerInfo] = list(timer_manager.timers.values())

    # Filter by name first
    name: str | None = None
    if "name" in slots:
        name = slots["name"]["value"]
        assert name is not None
        name_norm = _normalize_name(name)

        matching_timers = [t for t in matching_timers if t.name_normalized == name_norm]
        if not matching_timers:
            # No matches
            return matching_timers

    # Filter by area name
    area_name: str | None = None
    if "area" in slots:
        area_name = slots["area"]["value"]
        assert area_name is not None
        area_name_norm = _normalize_name(area_name)

        matching_timers = [t for t in matching_timers if t.area_name == area_name_norm]
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
        matching_timers = [
            t
            for t in matching_timers
            if (t.start_hours == start_hours)
            and (t.start_minutes == start_minutes)
            and (t.start_seconds == start_seconds)
        ]
        if not matching_timers:
            # No matches
            return matching_timers

    if not device_id:
        # Can't re-order based on area/floor
        return matching_timers

    # Use device id to order remaining timers
    device_registry = dr.async_get(hass)
    device = device_registry.async_get(device_id)
    if (device is None) or (device.area_id is None):
        return matching_timers

    area_registry = ar.async_get(hass)
    area = area_registry.async_get_area(device.area_id)
    if area is None:
        return matching_timers

    def area_floor_sort(timer: TimerInfo) -> int:
        """Sort by area, then floor."""
        if timer.area_id == area.id:
            return -2

        if timer.floor_id == area.floor_id:
            return -1

        return 0

    matching_timers.sort(key=area_floor_sort)

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

    async def async_handle(self, intent_obj: intent.Intent) -> intent.IntentResponse:
        """Handle the intent."""
        hass = intent_obj.hass
        timer_manager: TimerManager = hass.data[TIMER_DATA]
        slots = self.async_validate_slots(intent_obj.slots)

        name: str | None = None
        if "name" in slots:
            name = slots["name"]["value"]

        hours: int | None = None
        if "hours" in slots:
            hours = int(slots["hours"]["value"])

        minutes: int | None = None
        if "minutes" in slots:
            minutes = int(slots["minutes"]["value"])

        seconds: int | None = None
        if "seconds" in slots:
            seconds = int(slots["seconds"]["value"])

        timer_manager.start_timer(
            hours,
            minutes,
            seconds,
            language=intent_obj.language,
            device_id=intent_obj.device_id,
            name=name,
        )

        return intent_obj.create_response()


class CancelTimerIntentHandler(intent.IntentHandler):
    """Intent handler for cancelling a timer."""

    intent_type = intent.INTENT_CANCEL_TIMER
    description = "Cancels a timer"
    slot_schema = {
        vol.Any("start_hours", "start_minutes", "start_seconds"): cv.positive_int,
        vol.Optional("name"): cv.string,
        vol.Optional("area"): cv.string,
    }

    async def async_handle(self, intent_obj: intent.Intent) -> intent.IntentResponse:
        """Handle the intent."""
        hass = intent_obj.hass
        timer_manager: TimerManager = hass.data[TIMER_DATA]
        slots = self.async_validate_slots(intent_obj.slots)

        timer = _find_timer(hass, slots, intent_obj.device_id)
        timer_manager.cancel_timer(timer.id)

        return intent_obj.create_response()


class IncreaseTimerIntentHandler(intent.IntentHandler):
    """Intent handler for increasing the time of a timer."""

    intent_type = intent.INTENT_INCREASE_TIMER
    description = "Adds more time to a timer"
    slot_schema = {
        vol.Any("hours", "minutes", "seconds"): cv.positive_int,
        vol.Any("start_hours", "start_minutes", "start_seconds"): cv.positive_int,
        vol.Optional("name"): cv.string,
        vol.Optional("area"): cv.string,
    }

    async def async_handle(self, intent_obj: intent.Intent) -> intent.IntentResponse:
        """Handle the intent."""
        hass = intent_obj.hass
        timer_manager: TimerManager = hass.data[TIMER_DATA]
        slots = self.async_validate_slots(intent_obj.slots)

        total_seconds = _get_total_seconds(slots)
        timer = _find_timer(hass, slots, intent_obj.device_id)
        timer_manager.add_time(timer.id, total_seconds)

        return intent_obj.create_response()


class DecreaseTimerIntentHandler(intent.IntentHandler):
    """Intent handler for decreasing the time of a timer."""

    intent_type = intent.INTENT_DECREASE_TIMER
    description = "Removes time from a timer"
    slot_schema = {
        vol.Required(vol.Any("hours", "minutes", "seconds")): cv.positive_int,
        vol.Any("start_hours", "start_minutes", "start_seconds"): cv.positive_int,
        vol.Optional("name"): cv.string,
        vol.Optional("area"): cv.string,
    }

    async def async_handle(self, intent_obj: intent.Intent) -> intent.IntentResponse:
        """Handle the intent."""
        hass = intent_obj.hass
        timer_manager: TimerManager = hass.data[TIMER_DATA]
        slots = self.async_validate_slots(intent_obj.slots)

        total_seconds = _get_total_seconds(slots)
        timer = _find_timer(hass, slots, intent_obj.device_id)
        timer_manager.remove_time(timer.id, total_seconds)

        return intent_obj.create_response()


class PauseTimerIntentHandler(intent.IntentHandler):
    """Intent handler for pausing a running timer."""

    intent_type = intent.INTENT_PAUSE_TIMER
    description = "Pauses a running timer"
    slot_schema = {
        vol.Any("start_hours", "start_minutes", "start_seconds"): cv.positive_int,
        vol.Optional("name"): cv.string,
        vol.Optional("area"): cv.string,
    }

    async def async_handle(self, intent_obj: intent.Intent) -> intent.IntentResponse:
        """Handle the intent."""
        hass = intent_obj.hass
        timer_manager: TimerManager = hass.data[TIMER_DATA]
        slots = self.async_validate_slots(intent_obj.slots)

        timer = _find_timer(hass, slots, intent_obj.device_id)
        timer_manager.pause_timer(timer.id)

        return intent_obj.create_response()


class UnpauseTimerIntentHandler(intent.IntentHandler):
    """Intent handler for unpausing a paused timer."""

    intent_type = intent.INTENT_UNPAUSE_TIMER
    description = "Resumes a paused timer"
    slot_schema = {
        vol.Any("start_hours", "start_minutes", "start_seconds"): cv.positive_int,
        vol.Optional("name"): cv.string,
        vol.Optional("area"): cv.string,
    }

    async def async_handle(self, intent_obj: intent.Intent) -> intent.IntentResponse:
        """Handle the intent."""
        hass = intent_obj.hass
        timer_manager: TimerManager = hass.data[TIMER_DATA]
        slots = self.async_validate_slots(intent_obj.slots)

        timer = _find_timer(hass, slots, intent_obj.device_id)
        timer_manager.unpause_timer(timer.id)

        return intent_obj.create_response()


class TimerStatusIntentHandler(intent.IntentHandler):
    """Intent handler for reporting the status of a timer."""

    intent_type = intent.INTENT_TIMER_STATUS
    description = "Reports the current status of timers"
    slot_schema = {
        vol.Any("start_hours", "start_minutes", "start_seconds"): cv.positive_int,
        vol.Optional("name"): cv.string,
        vol.Optional("area"): cv.string,
    }

    async def async_handle(self, intent_obj: intent.Intent) -> intent.IntentResponse:
        """Handle the intent."""
        hass = intent_obj.hass
        slots = self.async_validate_slots(intent_obj.slots)

        statuses: list[dict[str, Any]] = []
        for timer in _find_timers(hass, slots, intent_obj.device_id):
            total_seconds = timer.seconds_left

            minutes, seconds = divmod(total_seconds, 60)
            hours, minutes = divmod(minutes, 60)

            # Get lower-precision time for feedback
            rounded_hours, rounded_minutes, rounded_seconds = _round_time(
                hours, minutes, seconds
            )

            statuses.append(
                {
                    ATTR_ID: timer.id,
                    ATTR_NAME: timer.name or "",
                    ATTR_DEVICE_ID: timer.device_id or "",
                    "language": timer.language,
                    "start_hours": timer.start_hours or 0,
                    "start_minutes": timer.start_minutes or 0,
                    "start_seconds": timer.start_seconds or 0,
                    "is_active": timer.is_active,
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
