"""Timer implementation for intents."""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
import logging
import time
from typing import Any, override

import probatio
from propcache.api import cached_property

from homeassistant.auth.permissions import AbstractPermissions
from homeassistant.auth.permissions.const import (
    CAT_ENTITIES,
    POLICY_CONTROL,
    POLICY_READ,
)
from homeassistant.components.timer_list import (
    DOMAIN as TIMER_LIST_DOMAIN,
    TimerItem,
    TimerListEntity,
    TimerStatus,
    async_get_timer_list_entity,
)
from homeassistant.const import ATTR_DEVICE_ID, ATTR_ID, ATTR_NAME
from homeassistant.core import Context, HomeAssistant, callback
from homeassistant.exceptions import Unauthorized, UnknownUser
from homeassistant.helpers import (
    area_registry as ar,
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
    intent,
)
from homeassistant.util import dt as dt_util, ulid as ulid_util

from .const import TIMER_DATA

_LOGGER = logging.getLogger(__name__)

TIMER_NOT_FOUND_RESPONSE = "timer_not_found"
MULTIPLE_TIMERS_MATCHED_RESPONSE = "multiple_timers_matched"
NO_TIMER_SUPPORT_RESPONSE = "no_timer_support"
NO_TIMER_COMMAND_RESPONSE = "no_timer_command"


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
    """Id of the device where the timer was set.

    May be None only if conversation_command is set.
    """

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

    conversation_command: str | None = None
    """Text of conversation command to execute when timer is finished.

    This command must be in the language used to set the timer.
    """

    conversation_agent_id: str | None = None
    """Id of the conversation agent used to set the timer.

    This agent will be used to execute the conversation command.
    """

    context: Context | None = None
    """Context of the request that set the timer.

    The conversation command runs as the user of this context.
    """

    _created_seconds: int = 0
    """Number of seconds on the timer when it was created."""

    def __post_init__(self) -> None:
        """Post initialization."""
        self._created_seconds = self.seconds

    @property
    def seconds_left(self) -> int:
        """Return number of seconds left on the timer."""
        if not self.is_active:
            return self.seconds

        now = time.monotonic_ns()
        seconds_running = int((now - self.updated_at) / 1e9)
        return max(0, self.seconds - seconds_running)

    @property
    def created_seconds(self) -> int:
        """Return number of seconds on the timer when it was created.

        This value is increased if time is added to the timer, exceeding its
        original created_seconds.
        """
        return self._created_seconds

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
        self._created_seconds = max(self._created_seconds, self.seconds)
        self.updated_at = time.monotonic_ns()

    def finish(self) -> None:
        """Finish the timer."""
        self.seconds = 0
        self.updated_at = time.monotonic_ns()
        self.is_active = False

    def to_timer_item(self, now: datetime, monotonic_now: int) -> TimerItem:
        """Snapshot a legacy timer using UTC timestamps."""
        remaining = timedelta(seconds=self.seconds_left)
        return TimerItem(
            timer_id=self.id,
            name=self.name,
            status=TimerStatus.ACTIVE if self.is_active else TimerStatus.PAUSED,
            created_duration=timedelta(
                hours=self.start_hours or 0,
                minutes=self.start_minutes or 0,
                seconds=self.start_seconds or 0,
            ),
            created_at=now
            - timedelta(microseconds=(monotonic_now - self.created_at) // 1000),
            total_duration=timedelta(seconds=self.created_seconds),
            finishes_at=now + remaining if self.is_active else None,
            paused_remaining=remaining if not self.is_active else None,
        )


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


class NoTimerCommandError(intent.IntentHandleError):
    """Error when a conversation command does not match any intent."""

    def __init__(self, command: str) -> None:
        """Initialize error."""
        super().__init__(
            f"Intent not recognized: {command}",
            NO_TIMER_COMMAND_RESPONSE,
        )


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

        # timer id -> timer
        self.timers: dict[str, TimerInfo] = {}
        self.timer_tasks: dict[str, asyncio.Task] = {}

        # device_id -> handler
        self.handlers: dict[str, TimerHandler] = {}

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

    def start_timer(
        self,
        device_id: str | None,
        hours: int | None,
        minutes: int | None,
        seconds: int | None,
        language: str,
        name: str | None = None,
        conversation_command: str | None = None,
        conversation_agent_id: str | None = None,
        context: Context | None = None,
    ) -> str:
        """Start a timer."""
        if (not conversation_command) and (device_id is None):
            raise ValueError("Conversation command must be set if no device id")

        if (not conversation_command) and (
            (device_id is None) or (not self.is_timer_device(device_id))
        ):
            raise TimersNotSupportedError(device_id)

        total_seconds = 0
        if hours is not None:
            total_seconds += 60 * 60 * hours

        if minutes is not None:
            total_seconds += 60 * minutes

        if seconds is not None:
            total_seconds += seconds

        timer_id = ulid_util.ulid_now()
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
            conversation_command=conversation_command,
            conversation_agent_id=conversation_agent_id,
            context=context,
        )

        # Fill in area/floor info
        device_registry = dr.async_get(self.hass)
        if device_id and (device := device_registry.async_get(device_id)):
            area_id = dr.async_get_effective_area_id(self.hass, device)
            timer.area_id = area_id
            area_registry = ar.async_get(self.hass)
            if area_id and (area := area_registry.async_get_area(area_id)):
                timer.area_name = _normalize_name(area.name)
                timer.floor_id = area.floor_id

        self.timers[timer_id] = timer
        self.timer_tasks[timer_id] = self.hass.async_create_background_task(
            self._wait_for_timer(timer_id, total_seconds, created_at),
            name=f"Timer {timer_id}",
        )

        if (not timer.conversation_command) and (timer.device_id in self.handlers):
            self.handlers[timer.device_id](TimerEventType.STARTED, timer)
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

    async def async_cancel_timer(self, timer_id: str) -> None:
        """Cancel a timer."""
        timer = self.timers.pop(timer_id, None)
        if timer is None:
            raise TimerNotFoundError

        if timer.is_active:
            task = self.timer_tasks.pop(timer_id)
            task.cancel()

        timer.cancel()

        if (not timer.conversation_command) and (timer.device_id in self.handlers):
            self.handlers[timer.device_id](TimerEventType.CANCELLED, timer)
        _LOGGER.debug(
            "Timer cancelled: id=%s, name=%s, seconds_left=%s, device_id=%s",
            timer_id,
            timer.name,
            timer.seconds_left,
            timer.device_id,
        )

    async def async_add_time(self, timer_id: str, duration: timedelta) -> None:
        """Add time to a timer, or remove it if duration is negative."""
        timer = self.timers.get(timer_id)
        if timer is None:
            raise TimerNotFoundError

        seconds = round(duration.total_seconds())
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

        if (not timer.conversation_command) and (timer.device_id in self.handlers):
            self.handlers[timer.device_id](TimerEventType.UPDATED, timer)

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

    async def async_pause_timer(self, timer_id: str) -> None:
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

        if (not timer.conversation_command) and (timer.device_id in self.handlers):
            self.handlers[timer.device_id](TimerEventType.UPDATED, timer)
        _LOGGER.debug(
            "Timer paused: id=%s, name=%s, seconds_left=%s, device_id=%s",
            timer_id,
            timer.name,
            timer.seconds_left,
            timer.device_id,
        )

    async def async_unpause_timer(self, timer_id: str) -> None:
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

        if (not timer.conversation_command) and (timer.device_id in self.handlers):
            self.handlers[timer.device_id](TimerEventType.UPDATED, timer)
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

        if timer.conversation_command:
            self.hass.async_create_background_task(
                self._async_run_conversation_command(timer),
                "timer assist command",
            )
        elif timer.device_id in self.handlers:
            self.handlers[timer.device_id](TimerEventType.FINISHED, timer)

        _LOGGER.debug(
            "Timer finished: id=%s, name=%s, device_id=%s",
            timer_id,
            timer.name,
            timer.device_id,
        )

    async def _async_run_conversation_command(self, timer: TimerInfo) -> None:
        """Run the delayed command of a finished timer."""
        from homeassistant.components.conversation import async_converse  # noqa: PLC0415

        assert timer.conversation_command is not None

        context = Context()
        if timer.context is not None:
            context = Context(user_id=timer.context.user_id, parent_id=timer.context.id)

        result = await async_converse(
            self.hass,
            timer.conversation_command,
            conversation_id=None,
            context=context,
            language=timer.language,
            agent_id=timer.conversation_agent_id,
            device_id=timer.device_id,
        )

        # Nothing is listening to the response, so an error is only visible here.
        if result.response.response_type is intent.IntentResponseType.ERROR:
            _LOGGER.warning(
                "Delayed command failed: command=%s, code=%s, response=%s",
                timer.conversation_command,
                result.response.error_code,
                result.response.speech.get("plain", {}).get("speech", ""),
            )

    def is_timer_device(self, device_id: str) -> bool:
        """Return True if device has been registered to handle timer events."""
        return device_id in self.handlers


@callback
def async_device_supports_timers(hass: HomeAssistant, device_id: str) -> bool:
    """Return True if a device has a timer list or handles timer events."""
    timer_manager: TimerManager | None = hass.data.get(TIMER_DATA)
    if timer_manager is None:
        return False
    return timer_manager.is_timer_device(device_id) or bool(
        _async_get_device_timer_list_entity_ids(hass, device_id)
    )


@callback
def _async_get_device_timer_list_entity_ids(
    hass: HomeAssistant, device_id: str
) -> list[str]:
    """Find a device's enabled timer lists in the entity registry."""
    return [
        entry.entity_id
        for entry in er.async_entries_for_device(er.async_get(hass), device_id)
        if entry.domain == TIMER_LIST_DOMAIN
    ]


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


@dataclass(frozen=True, kw_only=True)
class _VoiceTimer:
    """A timer that voice commands can act on.

    The timer lives in a timer list entity or, for a device that registered a
    timer handler instead, in the timer manager.
    """

    item: TimerItem
    device_id: str | None
    area_id: str | None
    area_name: str | None
    """Normalized name of the area."""
    floor_id: str | None
    language: str
    owner: TimerManager | TimerListEntity

    @property
    def name_normalized(self) -> str:
        """Return normalized timer name."""
        return _normalize_name(self.item.name or "")

    def as_speech_dict(self, now: datetime) -> dict[str, Any]:
        """Format timer status for a voice response."""
        item = self.item
        total_seconds = round(item.remaining_at(now).total_seconds())
        if isinstance(self.owner, TimerManager):
            # Preserve the units used to start legacy timers.
            legacy_timer = self.owner.timers[item.timer_id]
            start_hours = legacy_timer.start_hours or 0
            start_minutes = legacy_timer.start_minutes or 0
            start_seconds = legacy_timer.start_seconds or 0
        else:
            start_minutes, start_seconds = divmod(
                round(item.created_duration.total_seconds()), 60
            )
            start_hours, start_minutes = divmod(start_minutes, 60)

        minutes, seconds = divmod(total_seconds, 60)
        hours, minutes = divmod(minutes, 60)

        # Get lower-precision time for feedback
        rounded_hours, rounded_minutes, rounded_seconds = _round_time(
            hours, minutes, seconds
        )

        return {
            ATTR_ID: item.timer_id,
            ATTR_NAME: item.name or "",
            ATTR_DEVICE_ID: self.device_id or "",
            "language": self.language,
            "start_hours": start_hours,
            "start_minutes": start_minutes,
            "start_seconds": start_seconds,
            "is_active": item.status == TimerStatus.ACTIVE,
            "hours_left": hours,
            "minutes_left": minutes,
            "seconds_left": seconds,
            "rounded_hours_left": rounded_hours,
            "rounded_minutes_left": rounded_minutes,
            "rounded_seconds_left": rounded_seconds,
            "total_seconds_left": total_seconds,
        }

    async def async_cancel(self) -> None:
        """Cancel the timer."""
        await self.owner.async_cancel_timer(self.item.timer_id)

    async def async_add_time(self, seconds: int) -> None:
        """Add time to a timer, or remove it if seconds is negative."""
        await self.owner.async_add_time(self.item.timer_id, timedelta(seconds=seconds))

    async def async_pause(self) -> None:
        """Pause the timer."""
        await self.owner.async_pause_timer(self.item.timer_id)

    async def async_unpause(self) -> None:
        """Unpause the timer."""
        await self.owner.async_unpause_timer(self.item.timer_id)


async def _async_get_user_permissions(
    intent_obj: intent.Intent,
) -> AbstractPermissions | None:
    """Return the caller's permissions, if the intent has a user context."""
    if not (user_id := intent_obj.context.user_id):
        return None
    if (user := await intent_obj.hass.auth.async_get_user(user_id)) is None:
        raise UnknownUser(context=intent_obj.context, user_id=user_id)
    return user.permissions


async def _async_get_voice_timers(
    intent_obj: intent.Intent, permission: str
) -> list[_VoiceTimer]:
    """Return active and paused timers accessible to the caller."""
    hass = intent_obj.hass
    permissions = await _async_get_user_permissions(intent_obj)
    timer_manager: TimerManager = hass.data[TIMER_DATA]
    now = dt_util.utcnow()
    monotonic_now = time.monotonic_ns()
    timers = [
        _VoiceTimer(
            item=timer.to_timer_item(now, monotonic_now),
            owner=timer_manager,
            device_id=timer.device_id,
            area_id=timer.area_id,
            area_name=timer.area_name,
            floor_id=timer.floor_id,
            language=timer.language,
        )
        for timer in timer_manager.timers.values()
        if not timer.conversation_command
    ]

    for entry in er.async_get(hass).entities.values():
        if (
            entry.domain == TIMER_LIST_DOMAIN
            and not entry.disabled
            and (
                permissions is None
                or permissions.check_entity(entry.entity_id, permission)
            )
        ):
            timers.extend(
                _async_get_timer_list_voice_timers(hass, entry, intent_obj.language)
            )

    return timers


@callback
def _async_get_timer_list_voice_timers(
    hass: HomeAssistant, entity_entry: er.RegistryEntry, language: str
) -> list[_VoiceTimer]:
    """Return the active and paused timers of a timer list."""
    area_id = er.async_get_effective_area_id(hass, entity_entry)

    area_name: str | None = None
    floor_id: str | None = None
    if area_id and (area := ar.async_get(hass).async_get_area(area_id)):
        area_name = _normalize_name(area.name)
        floor_id = area.floor_id

    if (entity := async_get_timer_list_entity(hass, entity_entry.entity_id)) is None:
        return []

    return [
        _VoiceTimer(
            item=item,
            owner=entity,
            device_id=entity_entry.device_id,
            area_id=area_id,
            area_name=area_name,
            floor_id=floor_id,
            language=language,
        )
        for item in entity.timers
        if item.status in (TimerStatus.ACTIVE, TimerStatus.PAUSED)
    ]


async def _async_find_timer(
    intent_obj: intent.Intent,
    slots: dict[str, Any],
    status: TimerStatus | None = None,
) -> _VoiceTimer:
    """Match a single timer with constraints or raise an error."""
    hass = intent_obj.hass
    device_id = intent_obj.device_id
    matching_timers = await _async_get_voice_timers(intent_obj, POLICY_CONTROL)
    has_filter = False

    if status is not None:
        has_filter = True
        matching_timers = [t for t in matching_timers if t.item.status == status]

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
    start_total_seconds: int | None = None
    if _has_start_time(slots):
        has_filter = True
        start_total_seconds = _get_total_seconds(slots, "start_")
        matching_timers = [
            t
            for t in matching_timers
            if round(t.item.created_duration.total_seconds()) == start_total_seconds
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
            and (area_id := dr.async_get_effective_area_id(hass, device))
            and (area := area_registry.async_get_area(area_id))
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
        "Timer not found: name=%s, area=%s, start_seconds=%s, device_id=%s",
        name,
        area_name,
        start_total_seconds,
        device_id,
    )

    raise TimerNotFoundError


async def _async_find_timers(
    intent_obj: intent.Intent, slots: dict[str, Any], permission: str
) -> list[_VoiceTimer]:
    """Match multiple timers with constraints or raise an error."""
    hass = intent_obj.hass
    device_id = intent_obj.device_id
    matching_timers = await _async_get_voice_timers(intent_obj, permission)

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
    if _has_start_time(slots):
        start_total_seconds = _get_total_seconds(slots, "start_")
        matching_timers = [
            t
            for t in matching_timers
            if round(t.item.created_duration.total_seconds()) == start_total_seconds
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
    if device is None:
        return matching_timers
    area_id = dr.async_get_effective_area_id(hass, device)
    if area_id is None:
        return matching_timers

    area_registry = ar.async_get(hass)
    area = area_registry.async_get_area(area_id)
    if area is None:
        return matching_timers

    def area_floor_sort(timer: _VoiceTimer) -> int:
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


def _has_start_time(slots: dict[str, Any]) -> bool:
    """Return True if the slots name the duration a timer was started with."""
    return any(
        key in slots for key in ("start_hours", "start_minutes", "start_seconds")
    )


def _get_total_seconds(slots: dict[str, Any], prefix: str = "") -> int:
    """Return the total number of seconds from hours/minutes/seconds slots."""
    total_seconds = 0
    if f"{prefix}hours" in slots:
        total_seconds += 60 * 60 * int(slots[f"{prefix}hours"]["value"])

    if f"{prefix}minutes" in slots:
        total_seconds += 60 * int(slots[f"{prefix}minutes"]["value"])

    if f"{prefix}seconds" in slots:
        total_seconds += int(slots[f"{prefix}seconds"]["value"])

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
        probatio.Required(probatio.Any("hours", "minutes", "seconds")): cv.positive_int,
        probatio.Optional("name"): cv.string,
        probatio.Optional("conversation_command"): cv.string,
    }

    @override
    async def async_handle(self, intent_obj: intent.Intent) -> intent.IntentResponse:
        """Handle the intent."""
        hass = intent_obj.hass
        timer_manager: TimerManager = hass.data[TIMER_DATA]
        slots = self.async_validate_slots(intent_obj.slots)

        conversation_command: str | None = None
        if "conversation_command" in slots:
            conversation_command = slots["conversation_command"]["value"].strip()

        timer_list: TimerListEntity | None = None
        if intent_obj.device_id:
            for entity_id in _async_get_device_timer_list_entity_ids(
                hass, intent_obj.device_id
            ):
                if (
                    timer_list := async_get_timer_list_entity(hass, entity_id)
                ) is not None:
                    break

        if (
            (not conversation_command)
            and (timer_list is None)
            and not (
                intent_obj.device_id
                and timer_manager.is_timer_device(intent_obj.device_id)
            )
        ):
            # Fail early if this is not a delayed command
            raise TimersNotSupportedError(intent_obj.device_id)

        # Validate conversation command if provided
        if conversation_command and not await self._validate_conversation_command(
            intent_obj, conversation_command
        ):
            raise NoTimerCommandError(conversation_command)

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

        if (not conversation_command) and (timer_list is not None):
            permissions = await _async_get_user_permissions(intent_obj)
            if permissions is not None and not permissions.check_entity(
                timer_list.entity_id, POLICY_CONTROL
            ):
                raise Unauthorized(
                    context=intent_obj.context,
                    entity_id=timer_list.entity_id,
                    permission=POLICY_CONTROL,
                    perm_category=CAT_ENTITIES,
                )
            await timer_list.async_create_timer(
                name=name, duration=timedelta(seconds=_get_total_seconds(slots))
            )
            return intent_obj.create_response()

        timer_manager.start_timer(
            intent_obj.device_id,
            hours,
            minutes,
            seconds,
            language=intent_obj.language,
            name=name,
            conversation_command=conversation_command,
            conversation_agent_id=intent_obj.conversation_agent_id,
            context=intent_obj.context,
        )

        return intent_obj.create_response()

    async def _validate_conversation_command(
        self, intent_obj: intent.Intent, conversation_command: str
    ) -> bool:
        """Validate that a conversation command can be executed."""
        from homeassistant.components.conversation import (  # noqa: PLC0415
            ConversationInput,
            async_get_agent,
            default_agent,
        )

        # Only validate if using the default agent
        conversation_agent = async_get_agent(
            intent_obj.hass, intent_obj.conversation_agent_id
        )

        if conversation_agent is None or not isinstance(
            conversation_agent, default_agent.DefaultAgent
        ):
            return True  # Skip validation

        test_input = ConversationInput(
            text=conversation_command,
            context=intent_obj.context,
            conversation_id=None,
            device_id=intent_obj.device_id,
            satellite_id=intent_obj.satellite_id,
            language=intent_obj.language,
            agent_id=conversation_agent.entity_id,
        )

        # check for sentence trigger
        if (
            await conversation_agent.async_recognize_sentence_trigger(test_input)
        ) is not None:
            return True

        # check for intent
        if (await conversation_agent.async_recognize_intent(test_input)) is not None:
            return True

        return False


class CancelTimerIntentHandler(intent.IntentHandler):
    """Intent handler for cancelling a timer."""

    intent_type = intent.INTENT_CANCEL_TIMER
    description = "Cancels a timer"
    slot_schema = {
        probatio.Any("start_hours", "start_minutes", "start_seconds"): cv.positive_int,
        probatio.Optional("name"): cv.string,
        probatio.Optional("area"): cv.string,
    }

    @override
    async def async_handle(self, intent_obj: intent.Intent) -> intent.IntentResponse:
        """Handle the intent."""
        slots = self.async_validate_slots(intent_obj.slots)

        timer = await _async_find_timer(intent_obj, slots)
        await timer.async_cancel()
        return intent_obj.create_response()


class CancelAllTimersIntentHandler(intent.IntentHandler):
    """Intent handler for cancelling all timers."""

    intent_type = intent.INTENT_CANCEL_ALL_TIMERS
    description = "Cancels all timers"
    slot_schema = {
        probatio.Optional("area"): cv.string,
    }

    @override
    async def async_handle(self, intent_obj: intent.Intent) -> intent.IntentResponse:
        """Handle the intent."""
        slots = self.async_validate_slots(intent_obj.slots)
        canceled = 0

        for timer in await _async_find_timers(intent_obj, slots, POLICY_CONTROL):
            await timer.async_cancel()
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
        probatio.Any("hours", "minutes", "seconds"): cv.positive_int,
        probatio.Any("start_hours", "start_minutes", "start_seconds"): cv.positive_int,
        probatio.Optional("name"): cv.string,
        probatio.Optional("area"): cv.string,
    }

    @override
    async def async_handle(self, intent_obj: intent.Intent) -> intent.IntentResponse:
        """Handle the intent."""
        slots = self.async_validate_slots(intent_obj.slots)

        total_seconds = _get_total_seconds(slots)
        timer = await _async_find_timer(intent_obj, slots)
        await timer.async_add_time(total_seconds)
        return intent_obj.create_response()


class DecreaseTimerIntentHandler(intent.IntentHandler):
    """Intent handler for decreasing the time of a timer."""

    intent_type = intent.INTENT_DECREASE_TIMER
    description = "Removes time from a timer"
    slot_schema = {
        probatio.Required(probatio.Any("hours", "minutes", "seconds")): cv.positive_int,
        probatio.Any("start_hours", "start_minutes", "start_seconds"): cv.positive_int,
        probatio.Optional("name"): cv.string,
        probatio.Optional("area"): cv.string,
    }

    @override
    async def async_handle(self, intent_obj: intent.Intent) -> intent.IntentResponse:
        """Handle the intent."""
        slots = self.async_validate_slots(intent_obj.slots)

        total_seconds = _get_total_seconds(slots)
        timer = await _async_find_timer(intent_obj, slots)
        await timer.async_add_time(-total_seconds)
        return intent_obj.create_response()


class PauseTimerIntentHandler(intent.IntentHandler):
    """Intent handler for pausing a running timer."""

    intent_type = intent.INTENT_PAUSE_TIMER
    description = "Pauses a running timer"
    slot_schema = {
        probatio.Any("start_hours", "start_minutes", "start_seconds"): cv.positive_int,
        probatio.Optional("name"): cv.string,
        probatio.Optional("area"): cv.string,
    }

    @override
    async def async_handle(self, intent_obj: intent.Intent) -> intent.IntentResponse:
        """Handle the intent."""
        slots = self.async_validate_slots(intent_obj.slots)

        timer = await _async_find_timer(intent_obj, slots, status=TimerStatus.ACTIVE)
        await timer.async_pause()
        return intent_obj.create_response()


class UnpauseTimerIntentHandler(intent.IntentHandler):
    """Intent handler for unpausing a paused timer."""

    intent_type = intent.INTENT_UNPAUSE_TIMER
    description = "Resumes a paused timer"
    slot_schema = {
        probatio.Any("start_hours", "start_minutes", "start_seconds"): cv.positive_int,
        probatio.Optional("name"): cv.string,
        probatio.Optional("area"): cv.string,
    }

    @override
    async def async_handle(self, intent_obj: intent.Intent) -> intent.IntentResponse:
        """Handle the intent."""
        slots = self.async_validate_slots(intent_obj.slots)

        timer = await _async_find_timer(intent_obj, slots, status=TimerStatus.PAUSED)
        await timer.async_unpause()
        return intent_obj.create_response()


class TimerStatusIntentHandler(intent.IntentHandler):
    """Intent handler for reporting the status of a timer."""

    intent_type = intent.INTENT_TIMER_STATUS
    description = "Reports the current status of timers"
    slot_schema = {
        probatio.Any("start_hours", "start_minutes", "start_seconds"): cv.positive_int,
        probatio.Optional("name"): cv.string,
        probatio.Optional("area"): cv.string,
    }

    @override
    async def async_handle(self, intent_obj: intent.Intent) -> intent.IntentResponse:
        """Handle the intent."""
        slots = self.async_validate_slots(intent_obj.slots)

        timers = await _async_find_timers(intent_obj, slots, POLICY_READ)
        now = dt_util.utcnow()
        response = intent_obj.create_response()
        response.async_set_speech_slots(
            {"timers": [timer.as_speech_dict(now) for timer in timers]}
        )

        return response
