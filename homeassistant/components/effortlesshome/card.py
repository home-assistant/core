import logging

import voluptuous as vol

from homeassistant.components.websocket_api import async_register_command, decorators
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


@decorators.websocket_command(
    {
        vol.Required("type"): DOMAIN +"_updated",
    }
)
@decorators.async_response
async def handle_subscribe_updates(hass, connection, msg) -> None:
    """Handle subscribe updates."""

    @callback
    def handle_event(event: str, area_id: str, args: dict | None = None) -> None:
        """Forward events to websocket."""
        if args is None:
            args = {}
        data = dict(**args, event=event, area_id=area_id)
        connection.send_message(
            {"id": msg["id"], "type": "event", "event": {"data": data}}
        )

    connection.subscriptions[msg["id"]] = async_dispatcher_connect(
        hass, DOMAIN +"_event", handle_event
    )
    connection.send_result(msg["id"])


async def async_register_card(hass) -> None:
    """Publish event to lovelace when alarm changes."""
    async_register_command(hass, handle_subscribe_updates)
