"""Timer implementation for intents.

Timers are stored and scheduled by a ``timer_list`` entity per device (see
``homeassistant.components.assist_satellite``, which creates one for every
satellite device). ``TimerManager`` resolves a device's entity on demand and
delegates to it, and bridges the entity's generic update events back to the
legacy per-device ``TimerHandler`` callbacks used by
wyoming/esphome/voip/mobile_app to play sounds or send notifications.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from enum import StrEnum
from functools import partial
import logging
from typing import Any, override

from propcache.api import cached_property
import voluptuous as vol

from homeassistant.components.timer_list import (
    DATA_COMPONENT as TIMER_LIST_DATA_COMPONENT,
    DOMAIN as TIMER_LIST_DOMAIN,
    TimerItem,
    TimerListEntity,
    TimerListEvent,
    TimerListEventType,
    TimerStatus,
)
from homeassistant.const import ATTR_DEVICE_ID, ATTR_ID, ATTR_NAME
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers import (
    area_registry as ar,
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
    intent,
)
from homeassistant.util import dt as dt_util

from .const import TIMER_DATA

_LOGGER = logging.getLogger(__name__)

TIMER_NOT_FOUND_RESPONSE = "timer_not_found"
MULTIPLE_TIMERS_MATCHED_RESPONSE = "multiple_timers_matched"
NO_TIMER_SUPPORT_RESPONSE = "no_timer_support"


@dataclass
class TimerInfo:
    """Snapshot of a single timer, for voice matching and reporting.

    Built on demand from a ``timer_list`` entity's ``TimerItem``; timers are
    no longer stored here, so mutating a ``TimerInfo`` has no effect.
    """

    id: str
    """Unique id of the timer."""

    name: str | None
    """User-provided name for timer."""

    seconds: int
    """Number of seconds left on the timer, as of this snapshot."""

    device_id: str
    """Id of the device whose timer list this timer belongs to."""

    start_hours: int
    """Number of hours in the timer's original duration, normalized."""

    start_minutes: int
    """Number of minutes in the timer's original duration, normalized."""

    start_seconds: int
    """Number of seconds in the timer's original duration, normalized."""

    created_seconds: int
    """Number of seconds on the timer when it was created."""

    language: str
    """Language configured for Home Assistant."""

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
        return self.seconds

    @cached_property
    def name_normalized(self) -> str:
        """Return normalized timer name."""
        return _normalize_name(self.name or "")


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

_EVENT_TYPE_MAP: dict[TimerListEventType, TimerEventType] = {
    TimerListEventType.STARTED: TimerEventType.STARTED,
    TimerListEventType.UPDATED: TimerEventType.UPDATED,
    TimerListEventType.CANCELLED: TimerEventType.CANCELLED,
    TimerListEventType.FINISHED: TimerEventType.FINISHED,
}


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
    """Error when a timer intent is used from an unregistered device.

    The device isn't registered to handle timer events.
    """

    def __init__(self, device_id: str | None = None) -> None:
        """Initialize error."""
        super().__init__(
            f"Device does not support timers: device_id={device_id}",
            NO_TIMER_SUPPORT_RESPONSE,
        )


class TimerManager:
    """Manager for intent timers."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize timer manager."""
        self.hass = hass

        # device_id -> handler
        self.handlers: dict[str, TimerHandler] = {}

        # entity_id -> unsubscribe, so each entity's events are bridged once
        self._subscriptions: dict[str, CALLBACK_TYPE] = {}

    def register_handler(
        self, device_id: str, handler: TimerHandler
    ) -> Callable[[], None]:
        """Register a timer handler.

        Returns a callable to unregister.
        """
        self.handlers[device_id] = handler

        def unregister() -> None:
            self.handlers.pop(device_id)

        return unregister

    def is_timer_device(self, device_id: str) -> bool:
        """Return True if device has been registered to handle timer events."""
        return device_id in self.handlers

    @callback
    def _get_entity(self, device_id: str) -> TimerListEntity | None:
        """Return the timer_list entity for a device, if it has one.

        The list is provided by the device's own integration, so it may live on
        any platform; resolve it by device association rather than assuming the
        ``timer_list`` platform owns it.
        """
        entity_registry = er.async_get(self.hass)
        entity_id = next(
            (
                entry.entity_id
                for entry in er.async_entries_for_device(
                    entity_registry, device_id, include_disabled_entities=True
                )
                if entry.domain == TIMER_LIST_DOMAIN
            ),
            None,
        )
        if entity_id is None:
            return None

        component = self.hass.data[TIMER_LIST_DATA_COMPONENT]
        timer_entity = component.get_entity(entity_id)
        if timer_entity is None:
            return None

        if entity_id not in self._subscriptions:
            self._subscriptions[entity_id] = timer_entity.async_subscribe_updates(
                partial(self._async_handle_timer_list_event, device_id)
            )

        return timer_entity

    @callback
    def _async_handle_timer_list_event(
        self, device_id: str, event: TimerListEvent
    ) -> None:
        """Bridge a timer_list event to the legacy per-device timer handler."""
        event_type = _EVENT_TYPE_MAP.get(event.event_type)
        handler = self.handlers.get(device_id)
        if event_type is None or handler is None:
            return

        handler(event_type, _timer_info_from_item(self.hass, device_id, event.item))

    async def start_timer(
        self,
        device_id: str | None,
        hours: int | None,
        minutes: int | None,
        seconds: int | None,
        language: str,
        name: str | None = None,
    ) -> str:
        """Start a timer."""
        if device_id is None or (entity := self._get_entity(device_id)) is None:
            raise TimersNotSupportedError(device_id)

        total_seconds = 0
        if hours is not None:
            total_seconds += 60 * 60 * hours
        if minutes is not None:
            total_seconds += 60 * minutes
        if seconds is not None:
            total_seconds += seconds

        timer_id = await entity.async_start_timer(
            name=name, duration=timedelta(seconds=total_seconds)
        )

        _LOGGER.debug(
            "Timer started: id=%s, name=%s, hours=%s,"
            " minutes=%s, seconds=%s, device_id=%s",
            timer_id,
            name,
            hours,
            minutes,
            seconds,
            device_id,
        )

        return timer_id

    async def cancel_timer(self, device_id: str, timer_id: str) -> None:
        """Cancel a timer."""
        entity = self._get_entity(device_id)
        if entity is None:
            raise TimerNotFoundError
        await entity.async_cancel_timer(timer_id)
        _LOGGER.debug("Timer cancelled: id=%s, device_id=%s", timer_id, device_id)

    async def add_time(self, device_id: str, timer_id: str, seconds: int) -> None:
        """Add time to a timer."""
        if seconds == 0:
            # Don't bother rescheduling
            return

        entity = self._get_entity(device_id)
        if entity is None:
            raise TimerNotFoundError
        await entity.async_add_time(timer_id, timedelta(seconds=seconds))

        if seconds > 0:
            log_verb, log_seconds = "increased", seconds
        else:
            log_verb, log_seconds = "decreased", -seconds
        _LOGGER.debug(
            "Timer %s by %s second(s): id=%s, device_id=%s",
            log_verb,
            log_seconds,
            timer_id,
            device_id,
        )

    async def remove_time(self, device_id: str, timer_id: str, seconds: int) -> None:
        """Remove time from a timer."""
        await self.add_time(device_id, timer_id, -seconds)

    async def pause_timer(self, device_id: str, timer_id: str) -> None:
        """Pause a timer."""
        entity = self._get_entity(device_id)
        if entity is None:
            raise TimerNotFoundError
        await entity.async_pause_timer(timer_id)
        _LOGGER.debug("Timer paused: id=%s, device_id=%s", timer_id, device_id)

    async def unpause_timer(self, device_id: str, timer_id: str) -> None:
        """Unpause a timer."""
        entity = self._get_entity(device_id)
        if entity is None:
            raise TimerNotFoundError
        await entity.async_unpause_timer(timer_id)
        _LOGGER.debug("Timer unpaused: id=%s, device_id=%s", timer_id, device_id)


@callback
def async_device_supports_timers(hass: HomeAssistant, device_id: str) -> bool:
    """Return True if device has been registered to handle timer events."""
    timer_manager: TimerManager | None = hass.data.get(TIMER_DATA)
    if timer_manager is None:
        return False
    return timer_manager.is_timer_device(device_id)


@callback
def async_register_timer_handler(
    hass: HomeAssistant, device_id: str, handler: TimerHandler
) -> Callable[[], None]:
    """Register a handler for timer events.

    Returns a callable to unregister.
    """
    timer_manager: TimerManager = hass.data[TIMER_DATA]
    return timer_manager.register_handler(device_id, handler)


# -----------------------------------------------------------------------------


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


def _timer_info_from_item(
    hass: HomeAssistant, device_id: str, item: TimerItem
) -> TimerInfo:
    """Build a TimerInfo snapshot from a timer_list entity's TimerItem."""
    total_seconds = int(item.duration.total_seconds())
    start_hours, start_minutes, start_seconds = _normalize_start_time(
        None, None, total_seconds
    )

    area_id: str | None = None
    area_name: str | None = None
    floor_id: str | None = None
    device_registry = dr.async_get(hass)
    if device := device_registry.async_get(device_id):
        area_id = device.area_id
        if device.area_id:
            area_registry = ar.async_get(hass)
            if area := area_registry.async_get_area(device.area_id):
                area_name = _normalize_name(area.name)
                floor_id = area.floor_id

    return TimerInfo(
        id=item.timer_id,
        name=item.name,
        # Rounded (not truncated): a snapshot taken microseconds after the
        # timer started should still read as the full nominal duration.
        seconds=round(item.remaining_at(dt_util.utcnow()).total_seconds()),
        device_id=device_id,
        start_hours=start_hours,
        start_minutes=start_minutes,
        start_seconds=start_seconds,
        created_seconds=total_seconds,
        language=hass.config.language,
        is_active=item.status == TimerStatus.ACTIVE,
        area_id=area_id,
        area_name=area_name,
        floor_id=floor_id,
    )


def _all_timer_infos(hass: HomeAssistant) -> list[TimerInfo]:
    """Return snapshots of all active/paused timers across satellite devices.

    Only device-linked timer lists (each provided by a satellite's own
    integration) are considered, not a user's standalone local_timer_list
    helper, which has no associated device.
    """
    component = hass.data[TIMER_LIST_DATA_COMPONENT]
    infos: list[TimerInfo] = []
    for timer_entity in component.entities:
        registry_entry = timer_entity.registry_entry
        if registry_entry is None or registry_entry.device_id is None:
            continue
        device_id = registry_entry.device_id
        for item in timer_entity.timers:
            if item.status not in (TimerStatus.ACTIVE, TimerStatus.PAUSED):
                continue
            infos.append(_timer_info_from_item(hass, device_id, item))
    return infos


class FindTimerFilter(StrEnum):
    """Type of filter to apply when finding a timer."""

    ONLY_ACTIVE = "only_active"
    ONLY_INACTIVE = "only_inactive"


def _find_timer(
    hass: HomeAssistant,
    device_id: str | None,
    slots: dict[str, Any],
    find_filter: FindTimerFilter | None = None,
) -> TimerInfo:
    """Match a single timer with constraints or raise an error."""
    matching_timers: list[TimerInfo] = _all_timer_infos(hass)
    has_filter = False

    if find_filter:
        # Filter by active state
        has_filter = True
        if find_filter == FindTimerFilter.ONLY_ACTIVE:
            matching_timers = [t for t in matching_timers if t.is_active]
        elif find_filter == FindTimerFilter.ONLY_INACTIVE:
            matching_timers = [t for t in matching_timers if not t.is_active]

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
        norm_start = _normalize_start_time(start_hours, start_minutes, start_seconds)
        matching_timers = [
            t
            for t in matching_timers
            if (t.start_hours, t.start_minutes, t.start_seconds) == norm_start
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
        "Timer not found: name=%s, area=%s, hours=%s,"
        " minutes=%s, seconds=%s, device_id=%s",
        name,
        area_name,
        start_hours,
        start_minutes,
        start_seconds,
        device_id,
    )

    raise TimerNotFoundError


def _find_timers(
    hass: HomeAssistant, device_id: str | None, slots: dict[str, Any]
) -> list[TimerInfo]:
    """Match multiple timers with constraints or raise an error."""
    matching_timers: list[TimerInfo] = _all_timer_infos(hass)

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
        norm_start = _normalize_start_time(start_hours, start_minutes, start_seconds)
        matching_timers = [
            t
            for t in matching_timers
            if (t.start_hours, t.start_minutes, t.start_seconds) == norm_start
        ]
        if not matching_timers:
            # No matches
            return matching_timers

    if not device_id:
        # Can't order using area/floor
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

    @override
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

        await timer_manager.start_timer(
            intent_obj.device_id,
            hours,
            minutes,
            seconds,
            language=intent_obj.language,
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

    @override
    async def async_handle(self, intent_obj: intent.Intent) -> intent.IntentResponse:
        """Handle the intent."""
        hass = intent_obj.hass
        timer_manager: TimerManager = hass.data[TIMER_DATA]
        slots = self.async_validate_slots(intent_obj.slots)

        timer = _find_timer(hass, intent_obj.device_id, slots)
        await timer_manager.cancel_timer(timer.device_id, timer.id)
        return intent_obj.create_response()


class CancelAllTimersIntentHandler(intent.IntentHandler):
    """Intent handler for cancelling all timers."""

    intent_type = intent.INTENT_CANCEL_ALL_TIMERS
    description = "Cancels all timers"
    slot_schema = {
        vol.Optional("area"): cv.string,
    }

    @override
    async def async_handle(self, intent_obj: intent.Intent) -> intent.IntentResponse:
        """Handle the intent."""
        hass = intent_obj.hass
        timer_manager: TimerManager = hass.data[TIMER_DATA]
        slots = self.async_validate_slots(intent_obj.slots)
        canceled = 0

        for timer in _find_timers(hass, intent_obj.device_id, slots):
            await timer_manager.cancel_timer(timer.device_id, timer.id)
            canceled += 1

        response = intent_obj.create_response()
        speech_slots = {"canceled": canceled}
        if "area" in slots:
            speech_slots["area"] = slots["area"]["value"]

        response.async_set_speech_slots(speech_slots)

        return response


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

    @override
    async def async_handle(self, intent_obj: intent.Intent) -> intent.IntentResponse:
        """Handle the intent."""
        hass = intent_obj.hass
        timer_manager: TimerManager = hass.data[TIMER_DATA]
        slots = self.async_validate_slots(intent_obj.slots)

        total_seconds = _get_total_seconds(slots)
        timer = _find_timer(hass, intent_obj.device_id, slots)
        await timer_manager.add_time(timer.device_id, timer.id, total_seconds)
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

    @override
    async def async_handle(self, intent_obj: intent.Intent) -> intent.IntentResponse:
        """Handle the intent."""
        hass = intent_obj.hass
        timer_manager: TimerManager = hass.data[TIMER_DATA]
        slots = self.async_validate_slots(intent_obj.slots)

        total_seconds = _get_total_seconds(slots)
        timer = _find_timer(hass, intent_obj.device_id, slots)
        await timer_manager.remove_time(timer.device_id, timer.id, total_seconds)
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

    @override
    async def async_handle(self, intent_obj: intent.Intent) -> intent.IntentResponse:
        """Handle the intent."""
        hass = intent_obj.hass
        timer_manager: TimerManager = hass.data[TIMER_DATA]
        slots = self.async_validate_slots(intent_obj.slots)

        timer = _find_timer(
            hass, intent_obj.device_id, slots, find_filter=FindTimerFilter.ONLY_ACTIVE
        )
        await timer_manager.pause_timer(timer.device_id, timer.id)
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

    @override
    async def async_handle(self, intent_obj: intent.Intent) -> intent.IntentResponse:
        """Handle the intent."""
        hass = intent_obj.hass
        timer_manager: TimerManager = hass.data[TIMER_DATA]
        slots = self.async_validate_slots(intent_obj.slots)

        timer = _find_timer(
            hass, intent_obj.device_id, slots, find_filter=FindTimerFilter.ONLY_INACTIVE
        )
        await timer_manager.unpause_timer(timer.device_id, timer.id)
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

    @override
    async def async_handle(self, intent_obj: intent.Intent) -> intent.IntentResponse:
        """Handle the intent."""
        hass = intent_obj.hass
        slots = self.async_validate_slots(intent_obj.slots)

        statuses: list[dict[str, Any]] = []
        for timer in _find_timers(hass, intent_obj.device_id, slots):
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
                    ATTR_DEVICE_ID: timer.device_id,
                    "language": timer.language,
                    "start_hours": timer.start_hours,
                    "start_minutes": timer.start_minutes,
                    "start_seconds": timer.start_seconds,
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
