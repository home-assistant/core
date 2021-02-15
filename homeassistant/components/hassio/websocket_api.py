"""Websocekt API handlers for the hassio integration."""
import logging

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.components.websocket_api.connection import ActiveConnection
from homeassistant.core import HomeAssistant, callback

from .const import (
    EVENT_SUPERVISOR_EVENT,
    WS_DATA,
    WS_ID,
    WS_TYPE,
    WS_TYPE_EVENT,
    WS_TYPE_SNAPSHOT_NEW_FULL,
    WS_TYPE_SNAPSHOT_NEW_PARTIAL,
)
from .schema import (
    SCHEMA_SNAPSHOT_FULL,
    SCHEMA_SNAPSHOT_PARTIAL,
    SCHEMA_WEBSOCKET_EVENT,
)

_LOGGER: logging.Logger = logging.getLogger(__package__)


@callback
def async_load_websocket_api(hass: HomeAssistant):
    """Set up the websocket API."""
    websocket_api.async_register_command(hass, websocket_supervisor_event)
    websocket_api.async_register_command(hass, websocket_supervisor_snapshot_new_full)
    websocket_api.async_register_command(
        hass, websocket_supervisor_snapshot_new_partial
    )


@websocket_api.async_response
@websocket_api.websocket_command(
    {
        vol.Required(WS_TYPE): WS_TYPE_EVENT,
        vol.Required(WS_DATA): SCHEMA_WEBSOCKET_EVENT,
    }
)
async def websocket_supervisor_event(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict
):
    """Publish events from the Supervisor."""
    hass.bus.async_fire(EVENT_SUPERVISOR_EVENT, msg[WS_DATA])
    connection.send_result(msg[WS_ID])


@websocket_api.async_response
@websocket_api.websocket_command(
    {
        vol.Required(WS_TYPE): WS_TYPE_SNAPSHOT_NEW_FULL,
        vol.Required(WS_DATA): SCHEMA_SNAPSHOT_FULL,
    }
)
async def websocket_supervisor_snapshot_new_full(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict
):
    """Create new full snapshot."""
    result = False
    try:
        result = await hass.components.hassio.async_snapshot_new_full(msg[WS_DATA])
    except hass.components.hassio.HassioAPIError as err:
        _LOGGER.error("Failed to create full snapshot: %s", err)

    connection.send_result(msg[WS_ID], result)


@websocket_api.async_response
@websocket_api.websocket_command(
    {
        vol.Required(WS_TYPE): WS_TYPE_SNAPSHOT_NEW_PARTIAL,
        vol.Required(WS_DATA): SCHEMA_SNAPSHOT_PARTIAL,
    }
)
async def websocket_supervisor_snapshot_new_partial(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict
):
    """Create new partial snapshot."""
    result = False
    try:
        result = await hass.components.hassio.async_snapshot_new_partial(msg[WS_DATA])
    except hass.components.hassio.HassioAPIError as err:
        _LOGGER.error("Failed to create partial snapshot: %s", err)

    connection.send_result(msg[WS_ID], result)
