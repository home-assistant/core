"""HTML5 Websocket API."""

from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.service import async_get_config_entry

from .const import ATTR_VAPID_PUB_KEY, DOMAIN

WS_TYPE_APPKEY = "notify/html5/appkey"


@callback
def async_register_websocket_api(hass: HomeAssistant) -> None:
    """Register the websocket API."""

    websocket_api.async_register_command(hass, websocket_appkey)


@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_TYPE_APPKEY,
    }
)
@websocket_api.async_response
async def websocket_appkey(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Handle request for the VAPID public key."""
    entry = async_get_config_entry(hass, DOMAIN, None)
    connection.send_message(
        websocket_api.result_message(msg["id"], entry.data[ATTR_VAPID_PUB_KEY])
    )
