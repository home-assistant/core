"""Timer implementation for intents."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from functools import cached_property
import logging
import time
from typing import Any

import voluptuous as vol

from homeassistant.const import ATTR_DEVICE_ID, ATTR_ID, ATTR_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    area_registry as ar,
    config_validation as cv,
    device_registry as dr,
    intent,
)
from homeassistant.util import ulid

from .const import (
    ATTR_DATA,
    ATTR_LANGUAGE,
    ATTR_PAUSED,
    ATTR_SECONDS_LEFT,
    ATTR_START_HOURS,
    ATTR_START_MINUTES,
    ATTR_START_SECONDS,
    EVENT_INTENT_TIMER_CANCELLED,
    EVENT_INTENT_TIMER_FINISHED,
    EVENT_INTENT_TIMER_STARTED,
    EVENT_INTENT_TIMER_UPDATED,
    TIMER_DATA,
)

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

    task: asyncio.Task
    """Background task sleeping until timer is finished."""

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

    is_paused: bool = False
    """True if timer is currently paused."""

    data: dict[str, Any] | None = None
    """Extra data attached to timer that is passed to events."""

    area_id: str | None = None
    """Id of area that the device belongs to."""

    floor_id: str | None = None
    """Id of floor that the device's area belongs to."""

    @property
    def seconds_left(self) -> int:
        """Return number of seconds left on the timer."""
        if self.is_paused:
            return self.seconds

        now = time.monotonic_ns()
        seconds_running = int((now - self.updated_at) / 1e9)
        return max(0, self.seconds - seconds_running)

    @cached_property
    def name_normalized(self) -> str | None:
        """Return normalized timer name."""
        if self.name is None:
            return None

        return self.name.strip().casefold()

    def to_event(self) -> dict[str, Any]:
        """Convert to event data."""
        return {
            ATTR_ID: self.id,
            ATTR_NAME: self.name or "",
            ATTR_DEVICE_ID: self.device_id or "",
            ATTR_SECONDS_LEFT: self.seconds_left,
            ATTR_START_HOURS: self.start_hours or 0,
            ATTR_START_MINUTES: self.start_minutes or 0,
            ATTR_START_SECONDS: self.start_seconds or 0,
            ATTR_PAUSED: self.is_paused,
            ATTR_LANGUAGE: self.language,
            ATTR_DATA: self.data or {},
        }


class TimerNotFoundError(intent.IntentHandleError):
    """Error when a timer could not be found by name or start time."""

    def __init__(self) -> None:
        """Initialize error."""
        super().__init__(TIMER_NOT_FOUND_RESPONSE)


class MultipleTimersMatchedError(intent.IntentHandleError):
    """Error when multiple timers matched name or start time."""

    def __init__(self) -> None:
        """Initialize error."""
        super().__init__(MULTIPLE_TIMERS_MATCHED_RESPONSE)


class TimerManager:
    """Manager for intent timers."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize timer manager."""
        self.hass = hass
        self.area_registry = ar.async_get(hass)
        self.device_registry = dr.async_get(hass)

        # timer id -> timer
        self.timers: dict[str, TimerInfo] = {}

    async def start_timer(
        self,
        hours: int | None,
        minutes: int | None,
        seconds: int | None,
        language: str,
        device_id: str | None,
        name: str | None = None,
        data: dict[str, Any] | None = None,
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
            task=self.hass.async_create_background_task(
                self._wait_for_timer(timer_id, total_seconds, created_at),
                name=f"Timer {timer_id}",
            ),
            created_at=created_at,
            updated_at=created_at,
            data=data,
        )

        # Fill in area/floor info
        if device_id and (device := self.device_registry.async_get(device_id)):
            timer.area_id = device.area_id
            if device.area_id and (
                area := self.area_registry.async_get_area(device.area_id)
            ):
                timer.floor_id = area.floor_id

        self.timers[timer_id] = timer

        self.hass.bus.async_fire(EVENT_INTENT_TIMER_STARTED, timer.to_event())

        _LOGGER.debug(
            "Timer started: id=%s, name=%s, hours=%s, minutes=%s, seconds=%s, data=%s, device_id=%s",
            timer_id,
            name,
            hours,
            minutes,
            seconds,
            data,
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
                await self._timer_finished(timer_id)
        except asyncio.CancelledError:
            pass  # expected when timer is updated

    async def cancel_timer(self, timer_id: str) -> None:
        """Cancel a timer."""
        timer = self.timers.pop(timer_id, None)
        if timer is None:
            return

        # Capture event data before cancellation to get accurate seconds_left
        event_data = timer.to_event()

        timer.seconds = 0
        timer.updated_at = time.monotonic_ns()
        if not timer.is_paused:
            timer.task.cancel()

        self.hass.bus.async_fire(EVENT_INTENT_TIMER_CANCELLED, event_data)

        _LOGGER.debug(
            "Timer cancelled: id=%s, name=%s, seconds_left=%s, device_id=%s",
            timer_id,
            timer.name,
            timer.seconds_left,
            timer.device_id,
        )

    async def add_time(self, timer_id: str, seconds: int) -> None:
        """Add time to a timer."""
        if seconds == 0:
            return

        timer = self.timers.get(timer_id)
        if timer is None:
            return

        timer.seconds = max(0, timer.seconds_left + seconds)
        timer.updated_at = time.monotonic_ns()
        if not timer.is_paused:
            timer.task.cancel()
            timer.task = self.hass.async_create_background_task(
                self._wait_for_timer(timer_id, timer.seconds, timer.updated_at),
                name=f"Timer {timer_id}",
            )

        self.hass.bus.async_fire(EVENT_INTENT_TIMER_UPDATED, timer.to_event())

        if seconds > 0:
            log_verb = "increased"
            log_seconds = seconds
        else:
            log_verb = "decrease"
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

    async def remove_time(self, timer_id: str, seconds: int) -> None:
        """Remove time from a timer."""
        await self.add_time(timer_id, -seconds)

    async def pause_timer(self, timer_id: str) -> None:
        """Pauses a timer."""
        timer = self.timers.get(timer_id)
        if (timer is None) or timer.is_paused:
            return

        timer.seconds = timer.seconds_left
        timer.updated_at = time.monotonic_ns()
        timer.is_paused = True
        timer.task.cancel()

        self.hass.bus.async_fire(EVENT_INTENT_TIMER_UPDATED, timer.to_event())

        _LOGGER.debug(
            "Timer paused: id=%s, name=%s, seconds_left=%s, device_id=%s",
            timer_id,
            timer.name,
            timer.seconds_left,
            timer.device_id,
        )

    async def unpause_timer(self, timer_id: str) -> None:
        """Unpause a timer."""
        timer = self.timers.get(timer_id)
        if (timer is None) or (not timer.is_paused):
            return

        timer.is_paused = False
        timer.updated_at = time.monotonic_ns()
        timer.task = self.hass.async_create_background_task(
            self._wait_for_timer(timer_id, timer.seconds_left, timer.updated_at),
            name=f"Timer {timer.id}",
        )

        self.hass.bus.async_fire(EVENT_INTENT_TIMER_UPDATED, timer.to_event())

        _LOGGER.debug(
            "Timer unpaused: id=%s, name=%s, seconds_left=%s, device_id=%s",
            timer_id,
            timer.name,
            timer.seconds_left,
            timer.device_id,
        )

    async def _timer_finished(self, timer_id: str) -> None:
        """Call event handlers when a timer finishes."""
        timer = self.timers.pop(timer_id, None)
        if timer is None:
            return

        # Force seconds left to 0
        timer.seconds = 0
        timer.updated_at = time.monotonic_ns()
        self.hass.bus.async_fire(EVENT_INTENT_TIMER_FINISHED, timer.to_event())

        _LOGGER.debug(
            "Timer finished: id=%s, name=%s, device_id=%s",
            timer_id,
            timer.name,
            timer.device_id,
        )


def _find_timer(hass: HomeAssistant, slots: dict[str, Any]) -> TimerInfo:
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
        name_norm = name.strip().casefold()

        matching_timers = [t for t in matching_timers if t.name_normalized == name_norm]
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
    device_id: str | None = None
    if matching_timers and ("device_id" in slots):
        device_id = slots["device_id"]["value"]
        assert device_id is not None
        matching_device_timers = [
            t for t in matching_timers if (t.device_id == device_id)
        ]
        if len(matching_device_timers) == 1:
            # Only 1 match remaining
            return matching_device_timers[0]

        # Try area/floor
        if (
            (device := timer_manager.device_registry.async_get(device_id))
            and device.area_id
            and (area := timer_manager.area_registry.async_get_area(device.area_id))
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

    if has_filter and ("ordinal" in slots):
        ordinal = int(slots["ordinal"]["value"])
        if 0 <= ordinal < len(matching_timers):
            # Sort by creation time
            sorted_timers = sorted(matching_timers, key=lambda t: t.created_at)
            return sorted_timers[ordinal]

    if matching_timers:
        raise MultipleTimersMatchedError

    _LOGGER.warning(
        "Timer not found: name=%s, hours=%s, minutes=%s, seconds=%s, device_id=%s",
        name,
        start_hours,
        start_minutes,
        start_seconds,
        device_id,
    )

    raise TimerNotFoundError


def _find_timers(hass: HomeAssistant, slots: dict[str, Any]) -> list[TimerInfo]:
    """Match multiple timers with constraints or raise an error."""
    timer_manager: TimerManager = hass.data[TIMER_DATA]
    matching_timers: list[TimerInfo] = list(timer_manager.timers.values())

    # Filter by name first
    name: str | None = None
    if "name" in slots:
        name = slots["name"]["value"]
        assert name is not None
        name_norm = name.strip().casefold()

        matching_timers = [t for t in matching_timers if t.name_normalized == name_norm]
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

    if "device_id" not in slots:
        # Can't re-order based on area/floor
        return matching_timers

    # Use device id to order remaining timers
    device_id: str = slots["device_id"]["value"]
    device = timer_manager.device_registry.async_get(device_id)
    if (device is None) or (device.area_id is None):
        return matching_timers

    area = timer_manager.area_registry.async_get_area(device.area_id)
    if area is None:
        return matching_timers

    def area_floor_sort(timer: TimerInfo) -> int:
        if timer.area_id == area.id:
            return -2

        if timer.floor_id == area.floor_id:
            return -1

        return 0

    matching_timers.sort(key=area_floor_sort)

    return matching_timers


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


class SetTimerIntentHandler(intent.IntentHandler):
    """Intent handler for starting a new timer."""

    intent_type = intent.INTENT_SET_TIMER
    slot_schema = {
        vol.Required(vol.Any("hours", "minutes", "seconds")): cv.positive_int,
        vol.Optional("name"): cv.string,
        vol.Optional("device_id"): cv.string,
        vol.Optional("data"): dict,
    }

    async def async_handle(self, intent_obj: intent.Intent) -> intent.IntentResponse:
        """Handle the intent."""
        hass = intent_obj.hass
        timer_manager: TimerManager = hass.data[TIMER_DATA]
        slots = self.async_validate_slots(intent_obj.slots)

        device_id: str | None = None
        if "device_id" in slots:
            device_id = slots["device_id"]["value"]

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

        data: dict[str, Any] | None = None
        if "data" in slots:
            data = slots["data"]["value"]

        await timer_manager.start_timer(
            hours,
            minutes,
            seconds,
            language=intent_obj.language,
            device_id=device_id,
            name=name,
            data=data,
        )

        return intent_obj.create_response()


class CancelTimerIntentHandler(intent.IntentHandler):
    """Intent handler for cancelling a timer."""

    intent_type = intent.INTENT_CANCEL_TIMER
    slot_schema = {
        vol.Any("start_hours", "start_minutes", "start_seconds"): cv.positive_int,
        vol.Optional("name"): cv.string,
        vol.Optional("ordinal"): cv.positive_int,
        vol.Optional("device_id"): cv.string,
    }

    async def async_handle(self, intent_obj: intent.Intent) -> intent.IntentResponse:
        """Handle the intent."""
        hass = intent_obj.hass
        timer_manager: TimerManager = hass.data[TIMER_DATA]
        slots = self.async_validate_slots(intent_obj.slots)

        timer = _find_timer(hass, slots)
        await timer_manager.cancel_timer(timer.id)

        return intent_obj.create_response()


class IncreaseTimerIntentHandler(intent.IntentHandler):
    """Intent handler for increasing the time of a timer."""

    intent_type = intent.INTENT_INCREASE_TIMER
    slot_schema = {
        vol.Any("hours", "minutes", "seconds"): cv.positive_int,
        vol.Any("start_hours", "start_minutes", "start_seconds"): cv.positive_int,
        vol.Optional("name"): cv.string,
        vol.Optional("ordinal"): cv.positive_int,
        vol.Optional("device_id"): cv.string,
    }

    async def async_handle(self, intent_obj: intent.Intent) -> intent.IntentResponse:
        """Handle the intent."""
        hass = intent_obj.hass
        timer_manager: TimerManager = hass.data[TIMER_DATA]
        slots = self.async_validate_slots(intent_obj.slots)

        total_seconds = _get_total_seconds(slots)
        timer = _find_timer(hass, slots)
        await timer_manager.add_time(timer.id, total_seconds)

        return intent_obj.create_response()


class DecreaseTimerIntentHandler(intent.IntentHandler):
    """Intent handler for decreasing the time of a timer."""

    intent_type = intent.INTENT_DECREASE_TIMER
    slot_schema = {
        vol.Required(vol.Any("hours", "minutes", "seconds")): cv.positive_int,
        vol.Any("start_hours", "start_minutes", "start_seconds"): cv.positive_int,
        vol.Optional("name"): cv.string,
        vol.Optional("ordinal"): cv.positive_int,
        vol.Optional("device_id"): cv.string,
    }

    async def async_handle(self, intent_obj: intent.Intent) -> intent.IntentResponse:
        """Handle the intent."""
        hass = intent_obj.hass
        timer_manager: TimerManager = hass.data[TIMER_DATA]
        slots = self.async_validate_slots(intent_obj.slots)

        total_seconds = _get_total_seconds(slots)
        timer = _find_timer(hass, slots)
        await timer_manager.remove_time(timer.id, total_seconds)

        return intent_obj.create_response()


class PauseTimerIntentHandler(intent.IntentHandler):
    """Intent handler for pausing a running timer."""

    intent_type = intent.INTENT_PAUSE_TIMER
    slot_schema = {
        vol.Any("start_hours", "start_minutes", "start_seconds"): cv.positive_int,
        vol.Optional("name"): cv.string,
        vol.Optional("ordinal"): cv.positive_int,
        vol.Optional("device_id"): cv.string,
    }

    async def async_handle(self, intent_obj: intent.Intent) -> intent.IntentResponse:
        """Handle the intent."""
        hass = intent_obj.hass
        timer_manager: TimerManager = hass.data[TIMER_DATA]
        slots = self.async_validate_slots(intent_obj.slots)

        timer = _find_timer(hass, slots)
        await timer_manager.pause_timer(timer.id)

        return intent_obj.create_response()


class UnpauseTimerIntentHandler(intent.IntentHandler):
    """Intent handler for unpausing a paused timer."""

    intent_type = intent.INTENT_UNPAUSE_TIMER
    slot_schema = {
        vol.Any("start_hours", "start_minutes", "start_seconds"): cv.positive_int,
        vol.Optional("name"): cv.string,
        vol.Optional("ordinal"): cv.positive_int,
        vol.Optional("device_id"): cv.string,
    }

    async def async_handle(self, intent_obj: intent.Intent) -> intent.IntentResponse:
        """Handle the intent."""
        hass = intent_obj.hass
        timer_manager: TimerManager = hass.data[TIMER_DATA]
        slots = self.async_validate_slots(intent_obj.slots)

        timer = _find_timer(hass, slots)
        await timer_manager.unpause_timer(timer.id)

        return intent_obj.create_response()


class TimerStatusIntentHandler(intent.IntentHandler):
    """Intent handler for reporting the status of a timer."""

    intent_type = intent.INTENT_TIMER_STATUS
    slot_schema = {
        vol.Any("start_hours", "start_minutes", "start_seconds"): cv.positive_int,
        vol.Optional("name"): cv.string,
        vol.Optional("ordinal"): cv.positive_int,
        vol.Optional("device_id"): cv.string,
    }

    async def async_handle(self, intent_obj: intent.Intent) -> intent.IntentResponse:
        """Handle the intent."""
        hass = intent_obj.hass
        slots = self.async_validate_slots(intent_obj.slots)

        statuses: list[dict[str, Any]] = []
        for timer in _find_timers(hass, slots):
            total_seconds = timer.seconds_left

            minutes, seconds = divmod(total_seconds, 60)
            hours, minutes = divmod(minutes, 60)

            timer_status = timer.to_event()
            timer_status.update(
                {
                    "hours_left": hours,
                    "minutes_left": minutes,
                    "seconds_left": seconds,
                    "total_seconds_left": total_seconds,
                }
            )
            statuses.append(timer_status)

        response = intent_obj.create_response()
        response.async_set_speech_slots({"timers": statuses})

        return response
