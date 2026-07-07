"""The Timer list integration.

A timer list entity holds many independent countdown timers (its *items*),
mirroring how a to-do list holds many to-do items. The entity state is the
number of active timers. This module defines the abstract entity, the shared
data model, and the generic services/websocket API; storing timers and
scheduling their completion is left to concrete implementations such as
``local_timer_list``.
"""

from collections.abc import Callable
import copy
import dataclasses
from datetime import datetime, timedelta
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
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import dt as dt_util

from .const import (
    ATTR_DURATION,
    ATTR_STATUS,
    ATTR_TIMER_ID,
    DATA_COMPONENT,
    DOMAIN,
    TimerListEntityFeature,
    TimerListEventType,
    TimerListServices,
    TimerStatus,
)

_LOGGER = logging.getLogger(__name__)

ENTITY_ID_FORMAT = DOMAIN + ".{}"
PLATFORM_SCHEMA = cv.PLATFORM_SCHEMA
PLATFORM_SCHEMA_BASE = cv.PLATFORM_SCHEMA_BASE


@dataclasses.dataclass
class TimerItem:
    """A single timer within a timer list."""

    timer_id: str
    """Generated unique id of the timer."""

    name: str | None
    """Optional user-provided name."""

    status: TimerStatus
    """Current status of the timer."""

    duration: timedelta
    """Original duration the timer was created with."""

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
    """An entity that holds a list of independent countdown timers.

    This base class only provides the event/listener plumbing shared by the
    websocket API and triggers. Concrete implementations are responsible for
    storing timers and scheduling their completion.
    """

    _attr_should_poll = False

    def __init__(self) -> None:
        """Initialize the timer list."""
        self._update_listeners: list[Callable[[TimerListEvent], None]] = []

    @property
    @override
    def state(self) -> int:
        """Return the number of active timers."""
        return sum(timer.status == TimerStatus.ACTIVE for timer in self.timers)

    @property
    def timers(self) -> list[TimerItem]:
        """Return the timers in the list."""
        raise NotImplementedError

    async def async_start_timer(self, *, name: str | None, duration: timedelta) -> str:
        """Create and start a new timer, returning its id."""
        raise NotImplementedError

    async def async_pause_timer(self, timer_id: str) -> None:
        """Pause an active timer."""
        raise NotImplementedError

    async def async_unpause_timer(self, timer_id: str) -> None:
        """Resume a paused timer."""
        raise NotImplementedError

    async def async_cancel_timer(self, timer_id: str) -> None:
        """Cancel a timer."""
        raise NotImplementedError

    async def async_add_time(self, timer_id: str, duration: timedelta) -> None:
        """Add (or, with a negative duration, remove) time on a timer."""
        raise NotImplementedError

    async def async_remove_timer(self, timer_id: str) -> None:
        """Remove a timer from the list regardless of its status."""
        raise NotImplementedError

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

    @final
    @callback
    def _notify(self, event_type: TimerListEventType, timer: TimerItem) -> None:
        """Push a change event to subscribers and write entity state."""
        event = TimerListEvent(event_type=event_type, item=copy.copy(timer))
        for listener in list(self._update_listeners):
            listener(event)
        self.async_write_ha_state()


# Imported at the end so the reusable entity can subclass TimerListEntity above.
from .local import InMemoryTimerListEntity as InMemoryTimerListEntity  # noqa: E402


async def _async_start_timer(
    entity: TimerListEntity, call: ServiceCall
) -> dict[str, Any]:
    """Handle the start_timer service."""
    timer_id = await entity.async_start_timer(
        name=call.data.get(ATTR_NAME),
        duration=call.data[ATTR_DURATION],
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
