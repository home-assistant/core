"""Websocekt API handlers for the hassio integration."""
import logging

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.components.websocket_api.connection import ActiveConnection
from homeassistant.core import HomeAssistant, callback
import homeassistant.helpers.config_validation as cv

from .const import (
    ATTR_DATA,
    ATTR_ENDPOINT,
    ATTR_METHOD,
    ATTR_TIMEOUT,
    ATTR_WS_EVENT,
    DOMAIN,
    EVENT_SUPERVISOR_EVENT,
    WS_ID,
    WS_TYPE,
    WS_TYPE_API,
    WS_TYPE_EVENT,
)
from .handler import HassIO

SCHEMA_WEBSOCKET_EVENT = vol.Schema(
    {vol.Required(ATTR_WS_EVENT): cv.string},
    extra=vol.ALLOW_EXTRA,
)

_LOGGER: logging.Logger = logging.getLogger(__package__)


@callback
def async_load_websocket_api(hass: HomeAssistant):
    """Set up the websocket API."""
    websocket_api.async_register_command(hass, websocket_supervisor_event)
    websocket_api.async_register_command(hass, websocket_supervisor_api)


@websocket_api.async_response
@websocket_api.websocket_command(
    {
        vol.Required(WS_TYPE): WS_TYPE_EVENT,
        vol.Required(ATTR_DATA): SCHEMA_WEBSOCKET_EVENT,
    }
)
async def websocket_supervisor_event(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict
):
    """Publish events from the Supervisor."""
    hass.bus.async_fire(EVENT_SUPERVISOR_EVENT, msg[ATTR_DATA])
    connection.send_result(msg[WS_ID])


@websocket_api.require_admin
@websocket_api.async_response
@websocket_api.websocket_command(
    {
        vol.Required(WS_TYPE): WS_TYPE_API,
        vol.Required(ATTR_ENDPOINT): cv.string,
        vol.Required(ATTR_METHOD): cv.string,
        vol.Optional(ATTR_DATA): dict,
        vol.Optional(ATTR_TIMEOUT): cv.string,
    }
)
async def websocket_supervisor_api(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict
):
    """Websocket handler to call Supervisor API."""
    supervisor: HassIO = hass.data[DOMAIN]
    result = False
    try:
        result = await supervisor.send_command(
            msg[ATTR_ENDPOINT],
            method=msg[ATTR_METHOD],
            timeout=msg.get(ATTR_TIMEOUT, 10),
            payload=msg.get(ATTR_DATA, {}),
        )
    except hass.components.hassio.HassioAPIError as err:
        _LOGGER.error("Failed to to call %s - %s", msg[ATTR_ENDPOINT], err)
        connection.send_error(msg[WS_ID], err)
    else:
        connection.send_result(msg[WS_ID], result[ATTR_DATA])
