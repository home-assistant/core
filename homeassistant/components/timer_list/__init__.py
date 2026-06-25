"""The Timer list integration.

A timer list entity holds many independent countdown timers (its *items*),
mirroring how a to-do list holds many to-do items. The entity state is the
number of active timers. Timers are kept in memory only: they do not survive a
restart of Home Assistant in this first version (see the module-level notes on
``async_will_remove_from_hass``).
"""

from collections.abc import Callable
import copy
import dataclasses
from datetime import datetime, timedelta
from functools import partial
import logging
from typing import Any, final, override

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_NAME
from homeassistant.core import (
    CALLBACK_TYPE,
    HomeAssistant,
    ServiceCall,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import dt as dt_util, ulid as ulid_util

from .const import (
    ATTR_DURATION,
    ATTR_FINISH_ACTION,
    ATTR_STATUS,
    ATTR_TIMER_ID,
    DATA_COMPONENT,
    DOMAIN,
    TimerFinishAction,
    TimerListEntityFeature,
    TimerListEventType,
    TimerListServices,
    TimerStatus,
)

_LOGGER = logging.getLogger(__name__)

ENTITY_ID_FORMAT = DOMAIN + ".{}"
PLATFORM_SCHEMA = cv.PLATFORM_SCHEMA
PLATFORM_SCHEMA_BASE = cv.PLATFORM_SCHEMA_BASE

_FINISHED_STATUSES = (TimerStatus.FINISHED, TimerStatus.CANCELLED)


@dataclasses.dataclass
class TimerItem:
    """A single timer within a timer list."""

    timer_id: str
    """Generated unique id of the timer."""

    name: str | None
    """Optional user-provided name."""

    status: TimerStatus
    """Current status of the timer."""

    finish_action: TimerFinishAction
    """What happens to the timer once it finishes."""

    duration: timedelta
    """Original duration the timer was created with (used by ``restart``)."""

    created_at: datetime
    """When the timer was (re)started, in UTC."""

    finishes_at: datetime | None = None
    """Absolute time the timer will finish, in UTC. ``None`` unless active."""

    remaining: timedelta | None = None
    """Remaining time captured while paused. ``None`` unless paused."""

    finished_at: datetime | None = None
    """When the timer finished or was cancelled, in UTC."""

    def remaining_at(self, now: datetime) -> timedelta:
        """Return the time left on the timer relative to ``now``."""
        if self.status == TimerStatus.ACTIVE and self.finishes_at is not None:
            return max(timedelta(0), self.finishes_at - now)
        if self.status == TimerStatus.PAUSED and self.remaining is not None:
            return self.remaining
        return timedelta(0)


@dataclasses.dataclass(frozen=True)
class TimerListEvent:
    """A change to a timer, pushed to subscribers and triggers."""

    event_type: TimerListEventType
    item: TimerItem


@callback
def timer_to_dict(item: TimerItem, now: datetime) -> dict[str, Any]:
    """Serialize a timer item for the websocket API and triggers."""
    return {
        ATTR_TIMER_ID: item.timer_id,
        ATTR_NAME: item.name,
        ATTR_STATUS: item.status.value,
        ATTR_FINISH_ACTION: item.finish_action.value,
        "duration": item.duration.total_seconds(),
        "created_at": item.created_at.isoformat(),
        "finishes_at": item.finishes_at.isoformat() if item.finishes_at else None,
        "finished_at": item.finished_at.isoformat() if item.finished_at else None,
        "remaining": item.remaining_at(now).total_seconds(),
    }


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Timer list component."""
    component = hass.data[DATA_COMPONENT] = EntityComponent[TimerListEntity](
        _LOGGER, DOMAIN, hass
    )

    websocket_api.async_register_command(hass, websocket_handle_subscribe)
    websocket_api.async_register_command(hass, websocket_handle_list)

    component.async_register_entity_service(
        TimerListServices.START_TIMER,
        {
            vol.Optional(ATTR_NAME): cv.string,
            vol.Required(ATTR_DURATION): cv.positive_time_period,
            vol.Optional(
                ATTR_FINISH_ACTION, default=TimerFinishAction.REMOVE
            ): vol.Coerce(TimerFinishAction),
        },
        _async_start_timer,
        required_features=[TimerListEntityFeature.START_TIMER],
        supports_response=SupportsResponse.OPTIONAL,
    )
    component.async_register_entity_service(
        TimerListServices.PAUSE_TIMER,
        {vol.Required(ATTR_TIMER_ID): cv.string},
        "async_pause_timer",
        required_features=[TimerListEntityFeature.PAUSE_TIMER],
    )
    component.async_register_entity_service(
        TimerListServices.UNPAUSE_TIMER,
        {vol.Required(ATTR_TIMER_ID): cv.string},
        "async_unpause_timer",
        required_features=[TimerListEntityFeature.PAUSE_TIMER],
    )
    component.async_register_entity_service(
        TimerListServices.CANCEL_TIMER,
        {vol.Required(ATTR_TIMER_ID): cv.string},
        "async_cancel_timer",
        required_features=[TimerListEntityFeature.CANCEL_TIMER],
    )
    component.async_register_entity_service(
        TimerListServices.CANCEL_ALL_TIMERS,
        None,
        "async_cancel_all_timers",
        required_features=[TimerListEntityFeature.CANCEL_TIMER],
    )
    component.async_register_entity_service(
        TimerListServices.ADD_TIME,
        {
            vol.Required(ATTR_TIMER_ID): cv.string,
            vol.Required(ATTR_DURATION): cv.positive_time_period,
        },
        _async_add_time,
        required_features=[TimerListEntityFeature.ADD_TIME],
    )
    component.async_register_entity_service(
        TimerListServices.REMOVE_TIME,
        {
            vol.Required(ATTR_TIMER_ID): cv.string,
            vol.Required(ATTR_DURATION): cv.positive_time_period,
        },
        _async_remove_time,
        required_features=[TimerListEntityFeature.ADD_TIME],
    )
    component.async_register_entity_service(
        TimerListServices.REMOVE_TIMER,
        {vol.Required(ATTR_TIMER_ID): cv.string},
        "async_remove_timer",
    )
    component.async_register_entity_service(
        TimerListServices.CLEAR_FINISHED_TIMERS,
        None,
        "async_clear_finished_timers",
    )
    component.async_register_entity_service(
        TimerListServices.GET_TIMERS,
        {vol.Optional(ATTR_STATUS): vol.All(cv.ensure_list, [vol.Coerce(TimerStatus)])},
        _async_get_timers,
        supports_response=SupportsResponse.ONLY,
    )

    await component.async_setup(config)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    return await hass.data[DATA_COMPONENT].async_setup_entry(entry)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.data[DATA_COMPONENT].async_unload_entry(entry)


class TimerListEntity(Entity):
    """An entity that holds a list of independent countdown timers."""

    _attr_should_poll = False

    def __init__(self) -> None:
        """Initialize the timer list."""
        self._timers: dict[str, TimerItem] = {}
        self._cancel_callbacks: dict[str, CALLBACK_TYPE] = {}
        self._update_listeners: list[Callable[[TimerListEvent], None]] = []

    @property
    @override
    def state(self) -> int:
        """Return the number of active timers."""
        return sum(
            timer.status == TimerStatus.ACTIVE for timer in self._timers.values()
        )

    @property
    def timers(self) -> list[TimerItem]:
        """Return the timers in the list."""
        return list(self._timers.values())

    async def async_start_timer(
        self,
        *,
        name: str | None,
        duration: timedelta,
        finish_action: TimerFinishAction,
    ) -> str:
        """Create and start a new timer, returning its id."""
        now = dt_util.utcnow()
        timer_id = ulid_util.ulid_now()
        timer = TimerItem(
            timer_id=timer_id,
            name=name,
            status=TimerStatus.ACTIVE,
            finish_action=finish_action,
            duration=duration,
            created_at=now,
            finishes_at=now + duration,
        )
        self._timers[timer_id] = timer
        self._schedule(timer)
        self._notify(TimerListEventType.STARTED, timer)
        return timer_id

    async def async_pause_timer(self, timer_id: str) -> None:
        """Pause an active timer."""
        timer = self._get_timer(timer_id)
        if timer.status != TimerStatus.ACTIVE or timer.finishes_at is None:
            return
        timer.remaining = max(timedelta(0), timer.finishes_at - dt_util.utcnow())
        timer.finishes_at = None
        timer.status = TimerStatus.PAUSED
        self._unschedule(timer_id)
        self._notify(TimerListEventType.UPDATED, timer)

    async def async_unpause_timer(self, timer_id: str) -> None:
        """Resume a paused timer."""
        timer = self._get_timer(timer_id)
        if timer.status != TimerStatus.PAUSED or timer.remaining is None:
            return
        timer.finishes_at = dt_util.utcnow() + timer.remaining
        timer.remaining = None
        timer.status = TimerStatus.ACTIVE
        self._schedule(timer)
        self._notify(TimerListEventType.UPDATED, timer)

    async def async_cancel_timer(self, timer_id: str) -> None:
        """Cancel a timer.

        The timer is retained in the ``cancelled`` state only when its finish
        action is ``archive``; otherwise it is removed.
        """
        timer = self._get_timer(timer_id)
        self._unschedule(timer_id)
        timer.status = TimerStatus.CANCELLED
        timer.finishes_at = None
        timer.remaining = None
        timer.finished_at = dt_util.utcnow()
        self._notify(TimerListEventType.CANCELLED, timer)
        if timer.finish_action != TimerFinishAction.ARCHIVE:
            del self._timers[timer_id]
            self._notify(TimerListEventType.REMOVED, timer)

    async def async_cancel_all_timers(self) -> None:
        """Cancel every active or paused timer."""
        for timer_id in [
            timer.timer_id
            for timer in self._timers.values()
            if timer.status in (TimerStatus.ACTIVE, TimerStatus.PAUSED)
        ]:
            await self.async_cancel_timer(timer_id)

    async def async_add_time(self, timer_id: str, duration: timedelta) -> None:
        """Add (or, with a negative duration, remove) time on a timer."""
        timer = self._get_timer(timer_id)
        if timer.status == TimerStatus.ACTIVE and timer.finishes_at is not None:
            now = dt_util.utcnow()
            finishes_at = timer.finishes_at + duration
            if finishes_at <= now:
                self._unschedule(timer_id)
                self._async_timer_finished(timer_id, now)
                return
            timer.finishes_at = finishes_at
            self._schedule(timer)
        elif timer.status == TimerStatus.PAUSED and timer.remaining is not None:
            timer.remaining = max(timedelta(0), timer.remaining + duration)
        else:
            return
        self._notify(TimerListEventType.UPDATED, timer)

    async def async_remove_timer(self, timer_id: str) -> None:
        """Remove a timer from the list regardless of its status."""
        timer = self._get_timer(timer_id)
        self._unschedule(timer_id)
        del self._timers[timer_id]
        self._notify(TimerListEventType.REMOVED, timer)

    async def async_clear_finished_timers(self) -> None:
        """Remove all finished and cancelled (archived) timers."""
        for timer_id in [
            timer.timer_id
            for timer in self._timers.values()
            if timer.status in _FINISHED_STATUSES
        ]:
            timer = self._timers.pop(timer_id)
            self._notify(TimerListEventType.REMOVED, timer)

    def _get_timer(self, timer_id: str) -> TimerItem:
        """Return a timer by id or raise if it does not exist."""
        if (timer := self._timers.get(timer_id)) is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="timer_not_found",
                translation_placeholders={"timer_id": timer_id},
            )
        return timer

    @callback
    def _schedule(self, timer: TimerItem) -> None:
        """Schedule (or reschedule) the finish callback for a timer."""
        self._unschedule(timer.timer_id)
        assert timer.finishes_at is not None
        self._cancel_callbacks[timer.timer_id] = async_track_point_in_utc_time(
            self.hass,
            partial(self._async_timer_finished, timer.timer_id),
            timer.finishes_at,
        )

    @callback
    def _unschedule(self, timer_id: str) -> None:
        """Cancel a pending finish callback, if any."""
        if cancel := self._cancel_callbacks.pop(timer_id, None):
            cancel()

    @callback
    def _async_timer_finished(self, timer_id: str, now: datetime) -> None:
        """Handle a timer reaching its finish time."""
        self._cancel_callbacks.pop(timer_id, None)
        if (timer := self._timers.get(timer_id)) is None:
            return

        timer.status = TimerStatus.FINISHED
        timer.finishes_at = None
        timer.remaining = None
        timer.finished_at = dt_util.utcnow()
        self._notify(TimerListEventType.FINISHED, timer)

        if timer.finish_action == TimerFinishAction.REMOVE:
            self._timers.pop(timer_id, None)
            self._notify(TimerListEventType.REMOVED, timer)
        elif timer.finish_action == TimerFinishAction.RESTART:
            restarted_at = dt_util.utcnow()
            timer.status = TimerStatus.ACTIVE
            timer.created_at = restarted_at
            timer.finishes_at = restarted_at + timer.duration
            timer.finished_at = None
            self._schedule(timer)
            self._notify(TimerListEventType.STARTED, timer)

    @final
    @callback
    def async_subscribe_updates(
        self, listener: Callable[[TimerListEvent], None]
    ) -> CALLBACK_TYPE:
        """Subscribe to timer change events.

        Only future changes are pushed; the current set of timers is not
        replayed on subscribe.
        """
        self._update_listeners.append(listener)

        @callback
        def unsubscribe() -> None:
            self._update_listeners.remove(listener)

        return unsubscribe

    @callback
    def _notify(self, event_type: TimerListEventType, timer: TimerItem) -> None:
        """Push a change event to subscribers and write entity state."""
        event = TimerListEvent(event_type=event_type, item=copy.copy(timer))
        for listener in list(self._update_listeners):
            listener(event)
        self.async_write_ha_state()

    @override
    async def async_will_remove_from_hass(self) -> None:
        """Cancel all pending finish callbacks."""
        for cancel in self._cancel_callbacks.values():
            cancel()
        self._cancel_callbacks.clear()


async def _async_start_timer(
    entity: TimerListEntity, call: ServiceCall
) -> dict[str, Any]:
    """Handle the start_timer service."""
    timer_id = await entity.async_start_timer(
        name=call.data.get(ATTR_NAME),
        duration=call.data[ATTR_DURATION],
        finish_action=call.data[ATTR_FINISH_ACTION],
    )
    return {ATTR_TIMER_ID: timer_id}


async def _async_add_time(entity: TimerListEntity, call: ServiceCall) -> None:
    """Handle the add_time service."""
    await entity.async_add_time(call.data[ATTR_TIMER_ID], call.data[ATTR_DURATION])


async def _async_remove_time(entity: TimerListEntity, call: ServiceCall) -> None:
    """Handle the remove_time service."""
    await entity.async_add_time(call.data[ATTR_TIMER_ID], -call.data[ATTR_DURATION])


async def _async_get_timers(
    entity: TimerListEntity, call: ServiceCall
) -> dict[str, Any]:
    """Handle the get_timers service."""
    now = dt_util.utcnow()
    statuses: list[TimerStatus] | None = call.data.get(ATTR_STATUS)
    return {
        "timers": [
            timer_to_dict(timer, now)
            for timer in entity.timers
            if not statuses or timer.status in statuses
        ]
    }


@websocket_api.websocket_command(
    {
        vol.Required("type"): "timer_list/item/subscribe",
        vol.Required("entity_id"): cv.entity_domain(DOMAIN),
    }
)
@websocket_api.async_response
async def websocket_handle_subscribe(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Subscribe to timer changes for a timer list, with an initial snapshot."""
    entity_id: str = msg["entity_id"]
    if not (entity := hass.data[DATA_COMPONENT].get_entity(entity_id)):
        connection.send_error(
            msg["id"],
            websocket_api.ERR_NOT_FOUND,
            f"Timer list entity not found: {entity_id}",
        )
        return

    @callback
    def forward_event(event: TimerListEvent) -> None:
        """Forward a timer change event to the websocket connection."""
        connection.send_message(
            websocket_api.event_message(
                msg["id"],
                {
                    "type": "change",
                    "event_type": event.event_type.value,
                    "timer": timer_to_dict(event.item, dt_util.utcnow()),
                },
            )
        )

    connection.subscriptions[msg["id"]] = entity.async_subscribe_updates(forward_event)
    connection.send_result(msg["id"])

    now = dt_util.utcnow()
    connection.send_message(
        websocket_api.event_message(
            msg["id"],
            {
                "type": "timers",
                "timers": [timer_to_dict(timer, now) for timer in entity.timers],
            },
        )
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): "timer_list/item/list",
        vol.Required("entity_id"): cv.entity_domain(DOMAIN),
    }
)
@websocket_api.async_response
async def websocket_handle_list(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Return the current timers for a timer list."""
    entity_id: str = msg["entity_id"]
    if not (entity := hass.data[DATA_COMPONENT].get_entity(entity_id)):
        connection.send_error(
            msg["id"],
            websocket_api.ERR_NOT_FOUND,
            f"Timer list entity not found: {entity_id}",
        )
        return

    now = dt_util.utcnow()
    connection.send_result(
        msg["id"],
        {"timers": [timer_to_dict(timer, now) for timer in entity.timers]},
    )
