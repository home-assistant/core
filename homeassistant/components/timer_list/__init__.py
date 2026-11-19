"""The Timer list integration.

A timer list entity holds many independent countdown timers (its *items*),
mirroring how a to-do list holds many to-do items. The entity state is the
number of active timers. The platform provides the abstract entity, the shared
data model, and the generic services/websocket API; storing timers and
scheduling their completion is left to concrete implementations.
"""

import logging
from typing import Any

import probatio

from homeassistant.auth.permissions.const import POLICY_READ
from homeassistant.components import websocket_api
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import (
    CALLBACK_TYPE,
    DOMAIN as HOMEASSISTANT_DOMAIN,
    Event,
    EventStateChangedData,
    HomeAssistant,
    callback,
)
from homeassistant.exceptions import ConfigEntryError, Unauthorized
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import dt as dt_util

from .const import (
    ATTR_DELTA,
    ATTR_TIMERS,
    DATA_COMPONENT,
    DOMAIN,
    TimerListEntityFeature,
    TimerListEventType,
    TimerListServices,
    TimerStatus,
)
from .entity import TimerItem, TimerListEntity, TimerListEvent, timer_to_dict
from .services import async_setup_services

__all__ = [
    "DOMAIN",
    "ENTITY_ID_FORMAT",
    "PLATFORM_SCHEMA",
    "PLATFORM_SCHEMA_BASE",
    "TimerItem",
    "TimerListEntity",
    "TimerListEntityFeature",
    "TimerListEvent",
    "TimerListEventType",
    "TimerListServices",
    "TimerStatus",
]

_LOGGER = logging.getLogger(__name__)

ENTITY_ID_FORMAT = DOMAIN + ".{}"
PLATFORM_SCHEMA = cv.PLATFORM_SCHEMA
PLATFORM_SCHEMA_BASE = cv.PLATFORM_SCHEMA_BASE


@callback
def entity_became_available(event: Event[EventStateChangedData]) -> bool:
    """Return True if a state change means the entity is newly usable.

    A config entry reload builds a new entity object but leaves its registry
    entry alone, so this transition is the only signal that subscriptions held
    against the old object are now dangling.
    """
    new_state = event.data["new_state"]
    old_state = event.data["old_state"]
    if new_state is None or new_state.state == STATE_UNAVAILABLE:
        return False
    return old_state is None or old_state.state == STATE_UNAVAILABLE


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Timer list component."""
    component = hass.data[DATA_COMPONENT] = EntityComponent[TimerListEntity](
        _LOGGER, DOMAIN, hass
    )

    websocket_api.async_register_command(hass, websocket_handle_subscribe)
    websocket_api.async_register_command(hass, websocket_handle_list)

    async_setup_services(hass)

    await component.async_setup(config)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Set up a config entry."""
    if not await hass.data[DATA_COMPONENT].async_setup_entry(entry):
        raise ConfigEntryError(
            translation_domain=HOMEASSISTANT_DOMAIN,
            translation_key="platform_setup_failed",
            translation_placeholders={"platform": entry.domain, "domain": DOMAIN},
        )


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Unload a config entry."""
    await hass.data[DATA_COMPONENT].async_unload_entry(entry)


@websocket_api.websocket_command(
    {
        probatio.Required("type"): "timer_list/item/subscribe",
        probatio.Required("entity_id"): cv.entity_domain(DOMAIN),
    }
)
@websocket_api.async_response
async def websocket_handle_subscribe(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Subscribe to timer changes for a timer list, with an initial snapshot."""
    entity_id: str = msg["entity_id"]
    if not connection.user.permissions.check_entity(entity_id, POLICY_READ):
        raise Unauthorized(entity_id=entity_id)

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
        message: dict[str, Any] = {
            "type": "change",
            "event_type": event.event_type.value,
            "timer": timer_to_dict(event.item, dt_util.utcnow()),
        }
        if event.delta is not None:
            message[ATTR_DELTA] = event.delta.total_seconds()
        connection.send_message(websocket_api.event_message(msg["id"], message))

    @callback
    def send_snapshot(current: TimerListEntity) -> None:
        """Send the full current set of timers."""
        now = dt_util.utcnow()
        connection.send_message(
            websocket_api.event_message(
                msg["id"],
                {
                    "type": "timers",
                    ATTR_TIMERS: [
                        timer_to_dict(timer, now) for timer in current.timers
                    ],
                },
            )
        )

    unsub_entity: CALLBACK_TYPE | None = entity.async_subscribe_updates(forward_event)

    @callback
    def resubscribe(event: Event[EventStateChangedData]) -> None:
        """Rebind to the entity object a config entry reload replaced."""
        nonlocal unsub_entity
        if not entity_became_available(event):
            return
        if unsub_entity is not None:
            unsub_entity()
            unsub_entity = None
        if (new_entity := hass.data[DATA_COMPONENT].get_entity(entity_id)) is not None:
            unsub_entity = new_entity.async_subscribe_updates(forward_event)
            # The replacement may hold a different set of timers, and anything
            # that changed while the entry was unloaded went unreported, so the
            # client's pre-reload snapshot is no longer trustworthy.
            send_snapshot(new_entity)

    unsub_state = async_track_state_change_event(hass, [entity_id], resubscribe)

    @callback
    def unsubscribe() -> None:
        """Drop both the entity subscription and the reload watch."""
        unsub_state()
        if unsub_entity is not None:
            unsub_entity()

    connection.subscriptions[msg["id"]] = unsubscribe
    connection.send_result(msg["id"])

    send_snapshot(entity)


@websocket_api.websocket_command(
    {
        probatio.Required("type"): "timer_list/item/list",
        probatio.Required("entity_id"): cv.entity_domain(DOMAIN),
    }
)
@websocket_api.async_response
async def websocket_handle_list(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Return the current timers for a timer list."""
    entity_id: str = msg["entity_id"]
    if not connection.user.permissions.check_entity(entity_id, POLICY_READ):
        raise Unauthorized(entity_id=entity_id)

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
        {ATTR_TIMERS: [timer_to_dict(timer, now) for timer in entity.timers]},
    )
