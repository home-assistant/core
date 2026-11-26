"""WebSocket commands for timer lists."""

from typing import Any

import probatio

from homeassistant.auth.permissions.const import POLICY_READ
from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import Unauthorized
from homeassistant.helpers import config_validation as cv
from homeassistant.util import dt as dt_util

from .const import ATTR_DELTA, ATTR_TIMERS, DATA_COMPONENT, DOMAIN
from .entity import TimerListEvent


@callback
def async_setup(hass: HomeAssistant) -> None:
    """Register timer list WebSocket commands."""
    websocket_api.async_register_command(hass, websocket_handle_subscribe)
    websocket_api.async_register_command(hass, websocket_handle_list)


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

    if not entity.available:
        connection.send_error(
            msg["id"],
            websocket_api.ERR_HOME_ASSISTANT_ERROR,
            f"Timer list entity is unavailable: {entity_id}",
        )
        return

    @callback
    def forward_event(event: TimerListEvent) -> None:
        """Forward a timer change event to the websocket connection."""
        message: dict[str, Any] = {
            "type": "change",
            "event_type": event.event_type.value,
            "timer": event.item.as_dict(dt_util.utcnow()),
        }
        if event.delta is not None:
            message[ATTR_DELTA] = event.delta.total_seconds()
        connection.send_message(websocket_api.event_message(msg["id"], message))

    connection.subscriptions[msg["id"]] = entity.async_subscribe_updates(forward_event)
    connection.send_result(msg["id"])

    now = dt_util.utcnow()
    connection.send_message(
        websocket_api.event_message(
            msg["id"],
            {
                "type": "timers",
                ATTR_TIMERS: [timer.as_dict(now) for timer in entity.timers],
            },
        )
    )


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
        {ATTR_TIMERS: [timer.as_dict(now) for timer in entity.timers]},
    )
